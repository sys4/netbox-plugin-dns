from django.utils.translation import gettext_lazy as _
from dns import name as dns_name

from netbox.views import generic
from netbox_dns.filtersets import NameServerFilterSet, ZoneFilterSet
from netbox_dns.forms import (
    NameServerBulkEditForm,
    NameServerFilterForm,
    NameServerForm,
    NameServerImportForm,
)
from netbox_dns.models import NameServer, Zone
from netbox_dns.tables import NameServerTable, ZoneTable
from utilities.views import ViewTab, register_model_view

__all__ = (
    "NameServerView",
    "NameServerListView",
    "NameServerEditView",
    "NameServerDeleteView",
    "NameServerBulkEditView",
    "NameServerBulkImportView",
    "NameServerBulkDeleteView",
)


@register_model_view(NameServer, "list", path="", detail=False)
class NameServerListView(generic.ObjectListView):
    queryset = NameServer.objects.all()
    filterset = NameServerFilterSet
    filterset_form = NameServerFilterForm
    table = NameServerTable


@register_model_view(NameServer)
class NameServerView(generic.ObjectView):
    queryset = NameServer.objects.prefetch_related("zones")

    def get_extra_context(self, request, instance):
        name = dns_name.from_text(instance.name)
        if name.to_text() != name.to_unicode():
            return {
                "unicode_name": name.to_unicode(),
            }

        return {}


@register_model_view(NameServer, "add", detail=False)
@register_model_view(NameServer, "edit")
class NameServerEditView(generic.ObjectEditView):
    queryset = NameServer.objects.all()
    form = NameServerForm


@register_model_view(NameServer, "delete")
class NameServerDeleteView(generic.ObjectDeleteView):
    queryset = NameServer.objects.all()


@register_model_view(NameServer, "bulk_import", detail=False)
class NameServerBulkImportView(generic.BulkImportView):
    queryset = NameServer.objects.all()
    model_form = NameServerImportForm
    table = NameServerTable


@register_model_view(NameServer, "bulk_edit", path="edit", detail=False)
class NameServerBulkEditView(generic.BulkEditView):
    queryset = NameServer.objects.all()
    filterset = NameServerFilterSet
    table = NameServerTable
    form = NameServerBulkEditForm


@register_model_view(NameServer, "bulk_delete", path="delete", detail=False)
class NameServerBulkDeleteView(generic.BulkDeleteView):
    queryset = NameServer.objects.all()
    filterset = NameServerFilterSet
    table = NameServerTable


@register_model_view(NameServer, "zones")
class NameServerZoneListView(generic.ObjectChildrenView):
    queryset = NameServer.objects.prefetch_related("zones")
    child_model = Zone
    table = ZoneTable
    filterset = ZoneFilterSet
    template_name = "netbox_dns/zone/child.html"
    hide_if_empty = True

    tab = ViewTab(
        label=_("Zones"),
        permission="netbox_dns.view_zone",
        badge=lambda obj: obj.zones.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.zones.restrict(request.user, "view")


@register_model_view(NameServer, "soa_zones")
class NameServerSOAZoneListView(generic.ObjectChildrenView):
    queryset = NameServer.objects.prefetch_related("soa_zones")
    child_model = Zone
    table = ZoneTable
    filterset = ZoneFilterSet
    template_name = "netbox_dns/zone/child.html"
    hide_if_empty = True

    tab = ViewTab(
        label=_("SOA Zones"),
        permission="netbox_dns.view_zone",
        badge=lambda obj: obj.soa_zones.count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return parent.soa_zones.restrict(request.user, "view")
