import netaddr
from netaddr.core import AddrFormatError

import django_filters
from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filters import MultiValueCharFilter
from utilities.filtersets import register_filterset

from netbox_dns.models import (
    View,
    Zone,
    Registrar,
    RegistrationContact,
    NameServer,
    DNSSECPolicy,
)
from netbox_dns.choices import ZoneStatusChoices, ZoneEPPStatusChoices
from netbox_dns.filters import TimePeriodFilter

__all__ = ("ZoneFilterSet",)


@register_filterset
class ZoneFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = Zone

        fields = (
            "id",
            "soa_serial_auto",
            "rfc2317_parent_managed",
            "domain_status",
            "inline_signing",
        )

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    status = django_filters.MultipleChoiceFilter(
        choices=ZoneStatusChoices,
    )
    view_id = django_filters.ModelMultipleChoiceFilter(
        queryset=View.objects.all(),
    )
    view = django_filters.ModelMultipleChoiceFilter(
        queryset=View.objects.all(),
        field_name="view__name",
        to_field_name="name",
    )
    nameserver_id = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
        field_name="nameservers",
    )
    nameserver = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
        field_name="nameservers__name",
        to_field_name="name",
    )
    default_ttl = TimePeriodFilter()
    soa_mname_id = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
    )
    soa_mname = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
        field_name="soa_mname__name",
        to_field_name="name",
    )
    soa_rname = django_filters.CharFilter()
    soa_serial = django_filters.NumberFilter()
    soa_ttl = TimePeriodFilter()
    soa_refresh = TimePeriodFilter()
    soa_retry = TimePeriodFilter()
    soa_expire = TimePeriodFilter()
    soa_minimum = TimePeriodFilter()
    dnssec_policy_id = django_filters.ModelMultipleChoiceFilter(
        queryset=DNSSECPolicy.objects.all(),
    )
    dnssec_policy = django_filters.ModelMultipleChoiceFilter(
        queryset=DNSSECPolicy.objects.all(),
        field_name="dnssec_policy__name",
        to_field_name="name",
    )
    parental_agents = MultiValueCharFilter(
        method="filter_parental_agents",
    )
    rfc2317_prefix = MultiValueCharFilter(
        method="filter_rfc2317_prefix",
    )
    rfc2317_parent_zone_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Zone.objects.all(),
        field_name="rfc2317_parent_zone",
    )
    rfc2317_parent_zone = django_filters.ModelMultipleChoiceFilter(
        queryset=Zone.objects.all(),
        field_name="rfc2317_parent_zone__name",
        to_field_name="name",
    )
    registrar_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Registrar.objects.all(),
    )
    registrar = django_filters.ModelMultipleChoiceFilter(
        queryset=Registrar.objects.all(),
        field_name="registrar__name",
        to_field_name="name",
    )
    registry_domain_id = django_filters.CharFilter()
    expiration_date = django_filters.DateFromToRangeFilter()
    domain_status = django_filters.MultipleChoiceFilter(
        choices=ZoneEPPStatusChoices,
    )
    registrant_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
    )
    registrant = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
        field_name="registrant__contact_id",
        to_field_name="contact_id",
    )
    admin_c_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
    )
    admin_c = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
        field_name="admin_c__contact_id",
        to_field_name="contact_id",
    )
    tech_c_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
    )
    tech_c = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
        field_name="tech_c__contact_id",
        to_field_name="contact_id",
    )
    billing_c_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
    )
    billing_c = django_filters.ModelMultipleChoiceFilter(
        queryset=RegistrationContact.objects.all(),
        field_name="billing_c__contact_id",
        to_field_name="contact_id",
    )
    arpa_network = MultiValueCharFilter(
        method="filter_arpa_network",
    )
    active = django_filters.BooleanFilter()
    inline_signing = django_filters.BooleanFilter(
        method="filter_inline_signing",
    )

    def filter_parental_agents(self, queryset, name, value):
        if not value:
            return queryset

        query_values = []
        for v in value:
            try:
                query_values.append(str(netaddr.IPAddress(v)))
            except (AddrFormatError, ValueError):
                pass

        return queryset.filter(parental_agents__overlap=query_values)

    def filter_arpa_network(self, queryset, name, value):
        if not value:
            return queryset
        try:
            arpa_networks = [
                str(netaddr.IPNetwork(item)) for item in value if item.strip()
            ]
            if not arpa_networks:
                return queryset
            return queryset.filter(arpa_network__in=arpa_networks)

        except (netaddr.AddrFormatError, ValueError):
            return queryset.none()

    def filter_rfc2317_prefix(self, queryset, name, value):
        if not value:
            return queryset
        try:
            rfc2317_prefixes = [
                str(netaddr.IPNetwork(item)) for item in value if item.strip()
            ]
            if not rfc2317_prefixes:
                return queryset
            return queryset.filter(rfc2317_prefix__in=rfc2317_prefixes)

        except (netaddr.AddrFormatError, ValueError):
            return queryset.none()

    def filter_inline_signing(self, queryset, name, value):
        if value is None:
            return queryset

        if value:
            return queryset.filter(
                dnssec_policy__isnull=False, dnssec_policy__inline_signing=True
            )
        else:
            return queryset.filter(
                Q(
                    Q(dnssec_policy__isnull=True)
                    | Q(dnssec_policy__inline_signing=False)
                )
            )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(status__icontains=value)
            | Q(view__name__icontains=value)
            | Q(dnssec_policy__name__icontains=value)
            | Q(registrar__name__icontains=value)
            | Q(registry_domain_id__icontains=value)
            | Q(registrant__name__icontains=value)
            | Q(admin_c__name__icontains=value)
            | Q(tech_c__name__icontains=value)
            | Q(billing_c__name__icontains=value)
            | Q(comments__icontains=value)
        )
        return queryset.filter(qs_filter)
