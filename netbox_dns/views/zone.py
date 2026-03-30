from dns import name as dns_name

from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from netbox_dns.filtersets import ZoneFilterSet, RecordFilterSet
from netbox_dns.forms import (
    ZoneImportForm,
    ZoneForm,
    ZoneFilterForm,
    ZoneBulkEditForm,
)
from netbox_dns.models import Record, Zone
from netbox_dns.tables import (
    ZoneTable,
    RecordTable,
    ManagedRecordTable,
    DelegationRecordTable,
)

__all__ = (
    "ZoneView",
    "ZoneListView",
    "ZoneEditView",
    "ZoneDeleteView",
    "ZoneBulkImportView",
    "ZoneBulkEditView",
    "ZoneBulkDeleteView",
)


@register_model_view(Zone, "list", path="", detail=False)
class ZoneListView(generic.ObjectListView):
    queryset = Zone.objects.prefetch_related("view", "tags")
    filterset = ZoneFilterSet
    filterset_form = ZoneFilterForm
    table = ZoneTable


@register_model_view(Zone)
class ZoneView(generic.ObjectView):
    queryset = Zone.objects.prefetch_related(
        "view",
        "tags",
        "nameservers",
        "soa_mname",
        "records",
    )

    def get_extra_context(self, request, instance):
        ns_warnings, ns_errors = instance.check_nameservers()

        context = {
            "nameserver_warnings": ns_warnings,
            "nameserver_errors": ns_errors,
            "parent_zone": instance.parent_zone,
        }

        name = dns_name.from_text(instance.name)
        if name.to_text() != name.to_unicode():
            context["unicode_name"] = name.to_unicode()

        return context


@register_model_view(Zone, "add", detail=False)
@register_model_view(Zone, "edit")
class ZoneEditView(generic.ObjectEditView):
    queryset = Zone.objects.prefetch_related("view", "tags", "nameservers", "soa_mname")
    form = ZoneForm


@register_model_view(Zone, "delete")
class ZoneDeleteView(generic.ObjectDeleteView):
    queryset = Zone.objects.all()


@register_model_view(Zone, "bulk_import", detail=False)
class ZoneBulkImportView(generic.BulkImportView):
    queryset = Zone.objects.prefetch_related("view", "tags", "nameservers", "soa_mname")
    model_form = ZoneImportForm
    table = ZoneTable


@register_model_view(Zone, "bulk_edit", path="edit", detail=False)
class ZoneBulkEditView(generic.BulkEditView):
    queryset = Zone.objects.prefetch_related("view", "tags", "nameservers", "soa_mname")
    filterset = ZoneFilterSet
    table = ZoneTable
    form = ZoneBulkEditForm


@register_model_view(Zone, "bulk_delete", path="delete", detail=False)
class ZoneBulkDeleteView(generic.BulkDeleteView):
    queryset = Zone.objects.all()
    filterset = ZoneFilterSet
    table = ZoneTable


class RegistrationViewTab(ViewTab):
    def render(self, instance):
        if instance.is_registered:
            return super().render(instance)

        return None


@register_model_view(Zone, "registration")
class ZoneRegistrationView(generic.ObjectView):
    queryset = Zone.objects.all()
    template_name = "netbox_dns/zone/registration.html"

    tab = RegistrationViewTab(
        label=_("Registration"),
    )

    def get_extra_context(self, request, instance):
        expiration_warning, expiration_error = instance.check_expiration()

        context = {
            "expiration_warning": expiration_warning,
            "expiration_error": expiration_error,
        }

        return context


@register_model_view(Zone, "records")
class ZoneRecordListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Record
    table = RecordTable
    filterset = RecordFilterSet
    template_name = "netbox_dns/zone/record.html"
    hide_if_empty = True

    tab = ViewTab(
        label=_("Records"),
        permission="netbox_dns.view_record",
        badge=lambda obj: obj.records.filter(managed=False).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.records.restrict(request.user, "view").filter(managed=False)


@register_model_view(Zone, "managed_records")
class ZoneManagedRecordListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Record
    table = ManagedRecordTable
    filterset = RecordFilterSet
    template_name = "netbox_dns/zone/managed_record.html"

    tab = ViewTab(
        label=_("Managed Records"),
        permission="netbox_dns.view_record",
        badge=lambda obj: obj.records.filter(managed=True).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.records.restrict(request.user, "view").filter(managed=True)


@register_model_view(Zone, "delegation_records")
class ZoneDelegationRecordListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Record
    table = DelegationRecordTable
    filterset = RecordFilterSet
    template_name = "netbox_dns/zone/delegation_record.html"

    tab = ViewTab(
        label=_("Delegation Records"),
        permission="netbox_dns.view_record",
        badge=lambda obj: obj.delegation_records.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.delegation_records.restrict(request.user, "view")


@register_model_view(Zone, "parent_delegation_records")
class ZoneParentDelegationRecordListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Record
    table = DelegationRecordTable
    filterset = RecordFilterSet
    template_name = "netbox_dns/zone/delegation_record.html"

    tab = ViewTab(
        label=_("Parent Delegation Records"),
        permission="netbox_dns.view_record",
        badge=lambda obj: obj.ancestor_delegation_records.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.ancestor_delegation_records.restrict(request.user, "view")


@register_model_view(Zone, "rfc2317_child_zones")
class ZoneRFC2317ChildZoneListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Zone
    table = ZoneTable
    filterset = ZoneFilterSet
    template_name = "netbox_dns/zone/rfc2317_child_zone.html"

    tab = ViewTab(
        label=_("RFC2317 Child Zones"),
        permission="netbox_dns.view_zone",
        badge=lambda obj: obj.rfc2317_child_zones.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.rfc2317_child_zones.all()


@register_model_view(Zone, "child_zones")
class ZoneChildZoneListView(generic.ObjectChildrenView):
    queryset = Zone.objects.all()
    child_model = Zone
    table = ZoneTable
    filterset = ZoneFilterSet
    template_name = "netbox_dns/zone/child_zone.html"

    tab = ViewTab(
        label=_("Child Zones"),
        permission="netbox_dns.view_zone",
        badge=lambda obj: obj.child_zones.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.child_zones
