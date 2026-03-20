import django_filters

from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter

from netbox_dns.models import Registrar

__all__ = ("RegistrarFilterSet",)


@register_filterset
class RegistrarFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = Registrar

        fields = ("id",)

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    iana_id = django_filters.CharFilter()
    address = django_filters.CharFilter()
    referral_url = django_filters.CharFilter()
    whois_server = django_filters.CharFilter()
    abuse_email = django_filters.CharFilter()
    abuse_phone = django_filters.CharFilter()

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(iana_id=value)
            | Q(referral_url__icontains=value)
            | Q(whois_server__icontains=value)
            | Q(address__icontains=value)
            | Q(abuse_email__icontains=value)
            | Q(abuse_phone__icontains=value)
        )

        return queryset.filter(qs_filter)
