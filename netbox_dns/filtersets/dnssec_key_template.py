import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter

from netbox_dns.models import DNSSECKeyTemplate, DNSSECPolicy
from netbox_dns.choices import (
    DNSSECKeyTemplateTypeChoices,
    DNSSECKeyTemplateAlgorithmChoices,
    DNSSECKeyTemplateKeySizeChoices,
)
from netbox_dns.filters import TimePeriodFilter

__all__ = ("DNSSECKeyTemplateFilterSet",)


@register_filterset
class DNSSECKeyTemplateFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = DNSSECKeyTemplate

        fields = ("id",)

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    type = django_filters.MultipleChoiceFilter(
        choices=DNSSECKeyTemplateTypeChoices,
    )
    algorithm = django_filters.MultipleChoiceFilter(
        choices=DNSSECKeyTemplateAlgorithmChoices,
    )
    key_size = django_filters.MultipleChoiceFilter(
        choices=DNSSECKeyTemplateKeySizeChoices,
    )
    lifetime = TimePeriodFilter()
    policy_id = django_filters.ModelMultipleChoiceFilter(
        field_name="policies",
        queryset=DNSSECPolicy.objects.all(),
    )
    policy = django_filters.ModelMultipleChoiceFilter(
        field_name="policies__name",
        queryset=DNSSECPolicy.objects.all(),
        to_field_name="name",
    )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(Q(name__icontains=value) | Q(description__icontains=value))
        return queryset.filter(qs_filter)
