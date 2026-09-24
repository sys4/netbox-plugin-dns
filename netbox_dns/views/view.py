from django.utils.translation import gettext_lazy as _

from ipam.models import Prefix
from netbox.views import generic
from netbox_dns.filtersets import ViewFilterSet, ZoneFilterSet
from netbox_dns.forms import (
    ViewBulkEditForm,
    ViewFilterForm,
    ViewForm,
    ViewImportForm,
    ViewPrefixEditForm,
)
from netbox_dns.models import View, Zone
from netbox_dns.tables import ViewTable, ZoneTable
from netbox_dns.utilities import get_views_by_prefix
from utilities.views import ViewTab, register_model_view

__all__ = (
    "ViewView",
    "ViewListView",
    "ViewEditView",
    "ViewDeleteView",
    "ViewBulkImportView",
    "ViewBulkEditView",
    "ViewBulkDeleteView",
    "ViewPrefixEditView",
)


@register_model_view(View, "list", path="", detail=False)
class ViewListView(generic.ObjectListView):
    queryset = View.objects.all()
    table = ViewTable
    filterset = ViewFilterSet
    filterset_form = ViewFilterForm


@register_model_view(View)
class ViewView(generic.ObjectView):
    queryset = View.objects.prefetch_related("zones")


@register_model_view(View, "add", detail=False)
@register_model_view(View, "edit")
class ViewEditView(generic.ObjectEditView):
    queryset = View.objects.all()
    form = ViewForm


@register_model_view(View, "delete")
class ViewDeleteView(generic.ObjectDeleteView):
    queryset = View.objects.all()


@register_model_view(View, "bulk_import", detail=False)
class ViewBulkImportView(generic.BulkImportView):
    queryset = View.objects.all()
    model_form = ViewImportForm
    table = ViewTable


@register_model_view(View, "bulk_edit", path="edit", detail=False)
class ViewBulkEditView(generic.BulkEditView):
    queryset = View.objects.all()
    filterset = ViewFilterSet
    table = ViewTable
    form = ViewBulkEditForm


@register_model_view(View, "bulk_delete", path="delete", detail=False)
class ViewBulkDeleteView(generic.BulkDeleteView):
    queryset = View.objects.all()
    filterset = ViewFilterSet
    table = ViewTable


@register_model_view(Prefix, "views", path="assign-views")
class ViewPrefixEditView(generic.ObjectEditView):
    queryset = Prefix.objects.all()
    form = ViewPrefixEditForm
    template_name = "netbox_dns/view/prefix.html"

    def get_extra_context(self, request, instance):
        parents = instance.get_parents()
        if parents:
            return {
                "inherited_views": get_views_by_prefix(parents.last()),
                "inherited_from": parents.filter(netbox_dns_views__isnull=False).last(),
            }

        return {}


@register_model_view(View, "zones")
class ViewZoneListView(generic.ObjectChildrenView):
    queryset = View.objects.prefetch_related("zones")
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
