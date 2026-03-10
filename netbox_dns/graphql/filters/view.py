from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry_django import FilterLookup

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    from strawberry_django import FilterLookup as StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from ipam.graphql.filters import PrefixFilter

from netbox_dns.models import View

__all__ = ("NetBoxDNSViewFilter",)


@strawberry_django.filter_type(View, lookups=True)
class NetBoxDNSViewFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    default_view: FilterLookup[bool] | None = strawberry_django.filter_field()
    prefixes: (
        Annotated["PrefixFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()
