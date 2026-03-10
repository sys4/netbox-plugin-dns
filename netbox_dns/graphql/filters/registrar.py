from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    from strawberry_django import FilterLookup as StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter

if TYPE_CHECKING:
    from netbox.graphql.filter_lookups import IntegerLookup

from netbox_dns.models import Registrar

__all__ = ("NetBoxDNSRegistrarFilter",)


@strawberry_django.filter_type(Registrar, lookups=True)
class NetBoxDNSRegistrarFilter(PrimaryModelFilter):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    iana_id: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    address: StrFilterLookup[str] | None = strawberry_django.filter_field()
    referral_url: StrFilterLookup[str] | None = strawberry_django.filter_field()
    whois_server: StrFilterLookup[str] | None = strawberry_django.filter_field()
    abuse_email: StrFilterLookup[str] | None = strawberry_django.filter_field()
    abuse_phone: StrFilterLookup[str] | None = strawberry_django.filter_field()
