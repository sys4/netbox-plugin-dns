import django_filters

from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter
from ipam.models import Prefix

from netbox_dns.models import View

__all__ = ("ViewFilterSet",)


@register_filterset
class ViewFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = View

        fields = (
            "id",
            "default_view",
        )

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    prefix_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Prefix.objects.all(),
        field_name="prefixes",
    )
    prefix = django_filters.ModelMultipleChoiceFilter(
        queryset=Prefix.objects.all(),
        field_name="prefixes__prefix",
        to_field_name="prefix",
    )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(Q(name__icontains=value) | Q(description__icontains=value))

        return queryset.filter(qs_filter)
