import django_filters

from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter

from netbox_dns.models import DNSSECPolicy, DNSSECKeyTemplate, Zone, ZoneTemplate
from netbox_dns.choices import DNSSECPolicyStatusChoices
from netbox_dns.filters import TimePeriodFilter

__all__ = ("DNSSECPolicyFilterSet",)


@register_filterset
class DNSSECPolicyFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = DNSSECPolicy

        fields = (
            "id",
            "name",
            "description",
            "inline_signing",
            "create_cdnskey",
            "use_nsec3",
            "nsec3_opt_out",
            "nsec3_iterations",
            "nsec3_salt_size",
        )

    status = django_filters.MultipleChoiceFilter(
        choices=DNSSECPolicyStatusChoices,
    )
    cds_digest_types = MultiValueCharFilter(
        method="filter_cds_digest_types",
    )
    key_template = django_filters.ModelMultipleChoiceFilter(
        field_name="key_templates__name",
        queryset=DNSSECKeyTemplate.objects.all(),
        to_field_name="name",
    )
    key_template_id = django_filters.ModelMultipleChoiceFilter(
        field_name="key_templates",
        queryset=DNSSECKeyTemplate.objects.all(),
    )
    dnskey_ttl = TimePeriodFilter()
    purge_keys = TimePeriodFilter()
    publish_safety = TimePeriodFilter()
    retire_safety = TimePeriodFilter()
    signatures_jitter = TimePeriodFilter()
    signatures_refresh = TimePeriodFilter()
    signatures_validity = TimePeriodFilter()
    signatures_validity_dnskey = TimePeriodFilter()
    max_zone_ttl = TimePeriodFilter()
    zone_propagation_delay = TimePeriodFilter()
    parent_ds_ttl = TimePeriodFilter()
    parent_propagation_delay = TimePeriodFilter()
    zone = django_filters.ModelMultipleChoiceFilter(
        field_name="zones__name",
        queryset=Zone.objects.all(),
        to_field_name="name",
    )
    zone_id = django_filters.ModelMultipleChoiceFilter(
        field_name="zones",
        queryset=Zone.objects.all(),
    )
    zone_template = django_filters.ModelMultipleChoiceFilter(
        field_name="zone_templates__name",
        queryset=ZoneTemplate.objects.all(),
        to_field_name="name",
    )
    zone_template_id = django_filters.ModelMultipleChoiceFilter(
        field_name="zone_templates",
        queryset=ZoneTemplate.objects.all(),
    )

    def filter_cds_digest_types(self, queryset, name, value):
        if not value:
            return queryset

        return queryset.filter(cds_digest_types__overlap=value)

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(Q(name__icontains=value) | Q(description__icontains=value))
        return queryset.filter(qs_filter)
