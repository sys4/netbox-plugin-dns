from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from netbox_dns.filtersets import RegistrationContactFilterSet, ZoneFilterSet
from netbox_dns.forms import (
    RegistrationContactBulkEditForm,
    RegistrationContactFilterForm,
    RegistrationContactForm,
    RegistrationContactImportForm,
)
from netbox_dns.models import RegistrationContact, Zone
from netbox_dns.tables import RegistrationContactTable, ZoneTable
from utilities.views import ViewTab, register_model_view

__all__ = (
    "RegistrationContactView",
    "RegistrationContactEditView",
    "RegistrationContactListView",
    "RegistrationContactDeleteView",
    "RegistrationContactBulkImportView",
    "RegistrationContactBulkEditView",
    "RegistrationContactBulkDeleteView",
)


@register_model_view(RegistrationContact, "list", path="", detail=False)
class RegistrationContactListView(generic.ObjectListView):
    queryset = RegistrationContact.objects.all()
    table = RegistrationContactTable
    filterset = RegistrationContactFilterSet
    filterset_form = RegistrationContactFilterForm


@register_model_view(RegistrationContact)
class RegistrationContactView(generic.ObjectView):
    queryset = RegistrationContact.objects.all()


@register_model_view(RegistrationContact, "add", detail=False)
@register_model_view(RegistrationContact, "edit")
class RegistrationContactEditView(generic.ObjectEditView):
    queryset = RegistrationContact.objects.all()
    form = RegistrationContactForm


@register_model_view(RegistrationContact, "delete")
class RegistrationContactDeleteView(generic.ObjectDeleteView):
    queryset = RegistrationContact.objects.all()


@register_model_view(RegistrationContact, "bulk_import", detail=False)
class RegistrationContactBulkImportView(generic.BulkImportView):
    queryset = RegistrationContact.objects.all()
    model_form = RegistrationContactImportForm
    table = RegistrationContactTable


@register_model_view(RegistrationContact, "bulk_edit", path="edit", detail=False)
class RegistrationContactBulkEditView(generic.BulkEditView):
    queryset = RegistrationContact.objects.all()
    filterset = RegistrationContactFilterSet
    table = RegistrationContactTable
    form = RegistrationContactBulkEditForm


@register_model_view(RegistrationContact, "bulk_delete", path="delete", detail=False)
class RegistrationContactBulkDeleteView(generic.BulkDeleteView):
    queryset = RegistrationContact.objects.all()
    filterset = RegistrationContactFilterSet
    table = RegistrationContactTable


@register_model_view(RegistrationContact, "zones")
class RegistrationContactZoneListView(generic.ObjectChildrenView):
    queryset = RegistrationContact.objects.prefetch_related(
        "registrant_zones", "admin_c_zones", "tech_c_zones", "billing_c_zones"
    )
    child_model = Zone
    table = ZoneTable
    filterset = ZoneFilterSet
    template_name = "netbox_dns/zone/child.html"
    hide_if_empty = True

    tab = ViewTab(
        label=_("Zones"),
        permission="netbox_dns.view_zone",
        badge=lambda obj: len(obj.zones),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return Zone.objects.filter(
            Q(registrant=parent)
            | Q(admin_c=parent)
            | Q(tech_c=parent)
            | Q(billing_c=parent)
        ).restrict(request.user, "view")
