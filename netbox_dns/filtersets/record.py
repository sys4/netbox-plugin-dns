import netaddr

import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter

from ipam.models import IPAddress

from netbox_dns.models import View, Zone, Record
from netbox_dns.choices import RecordTypeChoices, RecordStatusChoices
from netbox_dns.filters import TimePeriodFilter

__all__ = ("RecordFilterSet",)


@register_filterset
class RecordFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = Record

        fields = (
            "id",
            "name",
            "description",
            "fqdn",
            "value",
            "disable_ptr",
            "managed",
        )

    ttl = TimePeriodFilter()
    status = django_filters.MultipleChoiceFilter(
        choices=RecordStatusChoices,
    )
    type = django_filters.MultipleChoiceFilter(
        choices=RecordTypeChoices,
    )
    zone_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Zone.objects.all(),
    )
    zone = django_filters.ModelMultipleChoiceFilter(
        queryset=Zone.objects.all(),
        field_name="zone__name",
        to_field_name="name",
    )
    view_id = django_filters.ModelMultipleChoiceFilter(
        queryset=View.objects.all(),
        field_name="zone__view",
    )
    view = django_filters.ModelMultipleChoiceFilter(
        queryset=View.objects.all(),
        field_name="zone__view__name",
        to_field_name="name",
    )
    address_record_id = django_filters.ModelMultipleChoiceFilter(
        field_name="address_records",
        queryset=Record.objects.all(),
    )
    ptr_record_id = django_filters.ModelMultipleChoiceFilter(
        field_name="ptr_record",
        queryset=Record.objects.all(),
    )
    rfc2317_cname_record_id = django_filters.ModelMultipleChoiceFilter(
        field_name="rfc2317_cname_record",
        queryset=Record.objects.all(),
    )
    ipam_ip_address_id = django_filters.ModelMultipleChoiceFilter(
        field_name="ipam_ip_address",
        queryset=IPAddress.objects.all(),
    )
    ip_address = MultiValueCharFilter(
        method="filter_ip_address",
    )
    active = django_filters.BooleanFilter()

    def filter_ip_address(self, queryset, name, value):
        if not value:
            return queryset
        try:
            ip_addresses = [
                str(netaddr.IPAddress(item)) for item in value if item.strip()
            ]
            if not ip_addresses:
                return queryset

            return queryset.filter(ip_address__in=ip_addresses)
        except (netaddr.AddrFormatError, ValueError):
            return queryset.none()

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(fqdn__icontains=value)
            | Q(description__icontains=value)
            | Q(value__icontains=value)
            | Q(zone__name__icontains=value)
        )
        return queryset.filter(qs_filter)
