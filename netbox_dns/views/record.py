from dns import name as dns_name

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view

from netbox_dns.filtersets import RecordFilterSet
from netbox_dns.forms import (
    RecordImportForm,
    RecordFilterForm,
    RecordForm,
    RecordBulkEditForm,
)
from netbox_dns.models import Record
from netbox_dns.choices import RecordTypeChoices
from netbox_dns.tables import RecordTable, ManagedRecordTable, RelatedRecordTable
from netbox_dns.utilities import (
    value_to_unicode,
    get_parent_zone_names,
    regex_from_list,
)

__all__ = (
    "RecordView",
    "RecordListView",
    "RecordEditView",
    "RecordDeleteView",
    "RecordBulkImportView",
    "RecordBulkEditView",
    "RecordBulkDeleteView",
    "ManagedRecordListView",
)


class CNAMEWarning(Exception):
    pass


@register_model_view(Record, "list", path="", detail=False)
class RecordListView(generic.ObjectListView):
    queryset = Record.objects.filter(managed=False).prefetch_related(
        "zone", "ptr_record"
    )
    filterset = RecordFilterSet
    filterset_form = RecordFilterForm
    table = RecordTable


@register_model_view(Record, "list_managed", path="managed", detail=False)
class ManagedRecordListView(generic.ObjectListView):
    queryset = Record.objects.filter(managed=True).prefetch_related(
        "ipam_ip_address", "address_records"
    )
    filterset = RecordFilterSet
    filterset_form = RecordFilterForm
    table = ManagedRecordTable
    actions = {"export": {"view"}}
    template_name = "netbox_dns/record/managed.html"


@register_model_view(Record)
class RecordView(generic.ObjectView):
    queryset = Record.objects.prefetch_related("zone", "ptr_record")

    def get_value_records(self, instance):
        value_fqdn = dns_name.from_text(instance.value_fqdn)

        cname_targets = Record.objects.filter(
            zone__view=instance.zone.view,
            fqdn=value_fqdn,
            active=True,
        )

        if cname_targets:
            return RelatedRecordTable(
                data=cname_targets,
            )

        if instance.zone.view.zones.filter(
            name__iregex=regex_from_list(
                get_parent_zone_names(instance.value_fqdn, min_labels=1)
            ),
            active=True,
        ).exists():
            raise (
                CNAMEWarning(
                    _(
                        "There is no matching target record for CNAME value {value}"
                    ).format(value=instance.value_fqdn)
                )
            )

        return None

    def get_cname_records(self, instance):
        cname_records = set(
            Record.objects.filter(
                zone__view=instance.zone.view,
                value=instance.fqdn,
                type=RecordTypeChoices.CNAME,
                active=True,
            )
        )

        parent_zones = instance.zone.view.zones.filter(
            name__iregex=regex_from_list(
                get_parent_zone_names(instance.fqdn, include_self=True)
            ),
        )

        for parent_zone in parent_zones:
            parent_cname_records = Record.objects.filter(
                zone__view=instance.zone.view,
                type=RecordTypeChoices.CNAME,
                zone=parent_zone,
                active=True,
            )
            cname_records = cname_records.union(
                {
                    record
                    for record in parent_cname_records
                    if record.value_fqdn == instance.fqdn
                }
            )

        if cname_records:
            return RelatedRecordTable(
                data=cname_records,
            )

        return None

    def get_extra_context(self, request, instance):
        context = {}

        name = dns_name.from_text(instance.name, origin=None)
        if name.to_text() != name.to_unicode():
            context["unicode_name"] = name.to_unicode()

        unicode_value = value_to_unicode(instance.value)
        if instance.value != unicode_value:
            context["unicode_value"] = unicode_value

        if instance.type == RecordTypeChoices.CNAME:
            try:
                cname_target_table = self.get_value_records(instance)
                if cname_target_table is not None:
                    cname_target_table.configure(request)
                context["cname_target_table"] = cname_target_table
            except CNAMEWarning as exc:
                context["cname_warning"] = str(exc)
        else:
            cname_table = self.get_cname_records(instance)
            if cname_table is not None:
                cname_table.configure(request)
            context["cname_table"] = cname_table

        if instance.ipam_ip_address is not None:
            context["ipam_ip_address"] = instance.ipam_ip_address
        elif instance.address_records is not None:
            address_record = instance.address_records.filter(
                ipam_ip_address__isnull=False
            ).first()
            if address_record is not None:
                context["ipam_ip_address"] = address_record.ipam_ip_address

        if not instance.managed:
            try:
                instance.check_zone_cut_conflict()
            except ValidationError:
                context["mask_warning"] = _(
                    "Record is masked by a child zone and may not be visible in DNS"
                )

        return context


@register_model_view(Record, "add", detail=False)
@register_model_view(Record, "edit")
class RecordEditView(generic.ObjectEditView):
    queryset = Record.objects.filter(managed=False).prefetch_related(
        "zone", "ptr_record"
    )
    form = RecordForm


@register_model_view(Record, "delete")
class RecordDeleteView(generic.ObjectDeleteView):
    queryset = Record.objects.filter(managed=False)


@register_model_view(Record, "bulk_import", detail=False)
class RecordBulkImportView(generic.BulkImportView):
    queryset = Record.objects.filter(managed=False).prefetch_related(
        "zone", "ptr_record"
    )
    model_form = RecordImportForm
    table = RecordTable


@register_model_view(Record, "bulk_edit", path="edit", detail=False)
class RecordBulkEditView(generic.BulkEditView):
    queryset = Record.objects.filter(managed=False).prefetch_related("zone")
    filterset = RecordFilterSet
    table = RecordTable
    form = RecordBulkEditForm


@register_model_view(Record, "bulk_delete", path="delete", detail=False)
class RecordBulkDeleteView(generic.BulkDeleteView):
    queryset = Record.objects.filter(managed=False)
    filterset = RecordFilterSet
    table = RecordTable
