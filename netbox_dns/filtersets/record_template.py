import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset

from netbox_dns.models import RecordTemplate, ZoneTemplate
from netbox_dns.choices import RecordTypeChoices, RecordStatusChoices
from netbox_dns.filters import TimePeriodFilter

__all__ = ("RecordTemplateFilterSet",)


@register_filterset
class RecordTemplateFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = RecordTemplate

        fields = (
            "id",
            "name",
            "description",
            "record_name",
            "value",
            "ttl",
            "disable_ptr",
        )

    ttl = TimePeriodFilter()
    type = django_filters.MultipleChoiceFilter(
        choices=RecordTypeChoices,
    )
    status = django_filters.MultipleChoiceFilter(
        choices=RecordStatusChoices,
    )
    zone_template = django_filters.ModelMultipleChoiceFilter(
        queryset=ZoneTemplate.objects.all(),
        field_name="zone_templates__name",
        to_field_name="name",
    )
    zone_template_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ZoneTemplate.objects.all(),
        field_name="zone_templates",
    )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(record_name__icontains=value)
            | Q(value__icontains=value)
        )
        return queryset.filter(qs_filter)
