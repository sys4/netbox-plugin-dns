import netaddr
from netaddr.core import AddrFormatError

import django_filters

from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filters import MultiValueCharFilter
from utilities.filtersets import register_filterset

from netbox_dns.models import (
    ZoneTemplate,
    RecordTemplate,
    Registrar,
    RegistrationContact,
    NameServer,
    DNSSECPolicy,
)

__all__ = ("ZoneTemplateFilterSet",)


@register_filterset
class ZoneTemplateFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    class Meta:
        model = ZoneTemplate

        fields = ("id",)

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    record_template_id = django_filters.ModelMultipleChoiceFilter(
        queryset=RecordTemplate.objects.all(),
        field_name="record_templates",
    )
    record_template = django_filters.ModelMultipleChoiceFilter(
        queryset=RecordTemplate.objects.all(),
        field_name="record_templates__name",
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
    soa_mname_id = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
        field_name="soa_mname",
    )
    soa_mname = django_filters.ModelMultipleChoiceFilter(
        queryset=NameServer.objects.all(),
        field_name="soa_mname__name",
        to_field_name="name",
    )
    soa_rname = django_filters.CharFilter()
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
    registrar_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Registrar.objects.all(),
    )
    registrar = django_filters.ModelMultipleChoiceFilter(
        queryset=Registrar.objects.all(),
        field_name="registrar__name",
        to_field_name="name",
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

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(soa_rname__icontains=value)
            | Q(registrar__name__icontains=value)
            | Q(registry_domain_id__icontains=value)
            | Q(registrant__name__icontains=value)
            | Q(admin_c__name__icontains=value)
            | Q(tech_c__name__icontains=value)
            | Q(billing_c__name__icontains=value)
        )
        return queryset.filter(qs_filter)
