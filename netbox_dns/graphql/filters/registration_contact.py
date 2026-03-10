import strawberry_django

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    from strawberry_django import FilterLookup as StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter

from netbox_dns.models import RegistrationContact

__all__ = ("NetBoxDNSRegistrationContactFilter",)


@strawberry_django.filter_type(RegistrationContact, lookups=True)
class NetBoxDNSRegistrationContactFilter(PrimaryModelFilter):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    contact_id: StrFilterLookup[str] | None = strawberry_django.filter_field()
    organization: StrFilterLookup[str] | None = strawberry_django.filter_field()
    street: StrFilterLookup[str] | None = strawberry_django.filter_field()
    city: StrFilterLookup[str] | None = strawberry_django.filter_field()
    state_province: StrFilterLookup[str] | None = strawberry_django.filter_field()
    postal_code: StrFilterLookup[str] | None = strawberry_django.filter_field()
    country: StrFilterLookup[str] | None = strawberry_django.filter_field()
    phone: StrFilterLookup[str] | None = strawberry_django.filter_field()
    phone_ext: StrFilterLookup[str] | None = strawberry_django.filter_field()
    fax: StrFilterLookup[str] | None = strawberry_django.filter_field()
    fax_ext: StrFilterLookup[str] | None = strawberry_django.filter_field()
    email: StrFilterLookup[str] | None = strawberry_django.filter_field()
