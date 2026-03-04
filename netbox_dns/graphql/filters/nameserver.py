from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry_django import StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from .zone import NetBoxDNSZoneFilter

from netbox_dns.models import NameServer

__all__ = ("NetBoxDNSNameServerFilter",)


@strawberry_django.filter_type(NameServer, lookups=True)
class NetBoxDNSNameServerFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    zones: (
        Annotated["NetBoxDNSZoneFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
    soa_zones: (
        Annotated["NetBoxDNSZoneFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
