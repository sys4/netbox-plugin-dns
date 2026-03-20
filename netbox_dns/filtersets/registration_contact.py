import django_filters

from django.db.models import Q

from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset
from utilities.filters import MultiValueCharFilter

from netbox_dns.models import RegistrationContact

__all__ = ("RegistrationContactFilterSet",)


@register_filterset
class RegistrationContactFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = RegistrationContact

        fields = ("id",)

    name = MultiValueCharFilter()
    description = django_filters.CharFilter()
    contact_id = django_filters.NumberFilter()
    organization = django_filters.CharFilter()
    street = django_filters.CharFilter()
    city = django_filters.CharFilter()
    state_province = django_filters.CharFilter()
    postal_code = django_filters.CharFilter()
    country = django_filters.CharFilter()
    phone = django_filters.CharFilter()
    phone_ext = django_filters.CharFilter()
    fax = django_filters.CharFilter()
    fax_ext = django_filters.CharFilter()
    email = django_filters.CharFilter()

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(contact_id__icontains=value)
            | Q(organization__icontains=value)
            | Q(city__icontains=value)
            | Q(state_province__icontains=value)
            | Q(street__icontains=value)
            | Q(country=value)
        )

        return queryset.filter(qs_filter)
