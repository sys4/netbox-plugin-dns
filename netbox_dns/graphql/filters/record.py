from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry.scalars import ID
from strawberry_django import FilterLookup, StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from ipam.graphql.filters import IPAddressFilter
    from netbox.graphql.filter_lookups import IntegerLookup
    from .enums import (
        NetBoxDNSRecordStatusEnum,
        NetBoxDNSRecordTypeEnum,
    )
    from .view import NetBoxDNSViewFilter
    from .zone import NetBoxDNSZoneFilter

from netbox_dns.models import Record

__all__ = ("NetBoxDNSRecordFilter",)


@strawberry_django.filter_type(Record, lookups=True)
class NetBoxDNSRecordFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    fqdn: StrFilterLookup[str] | None = strawberry_django.filter_field()
    view: (
        Annotated["NetBoxDNSViewFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
    view_id: ID | None = strawberry_django.filter_field()
    zone: (
        Annotated["NetBoxDNSZoneFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
    zone_id: ID | None = strawberry_django.filter_field()
    type: (
        Annotated[
            "NetBoxDNSRecordTypeEnum", strawberry.lazy("netbox_dns.graphql.enums")
        ]
        | None
    ) = strawberry_django.filter_field()
    ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    value: StrFilterLookup[str] | None = strawberry_django.filter_field()
    disable_ptr: FilterLookup[bool] | None = strawberry_django.filter_field()
    status: (
        Annotated[
            "NetBoxDNSRecordStatusEnum", strawberry.lazy("netbox_dns.graphql.enums")
        ]
        | None
    ) = strawberry_django.filter_field()
    managed: FilterLookup[bool] | None = strawberry_django.filter_field()
    address_record: (
        Annotated[
            "NetBoxDNSRecordFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    address_record_id: ID | None = strawberry_django.filter_field()
    ptr_record: (
        Annotated[
            "NetBoxDNSRecordFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    ptr_record_id: ID | None = strawberry_django.filter_field()
    rfc2317_cname_record: (
        Annotated[
            "NetBoxDNSRecordFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    ipam_ip_address: (
        Annotated["IPAddressFilter", strawberry.lazy("ipam.graphql.filters")] | None
    ) = strawberry_django.filter_field()
    ipam_ip_address_id: ID | None = strawberry_django.filter_field()

    ip_address: StrFilterLookup[str] | None = strawberry_django.filter_field()
    active: FilterLookup[bool] | None = strawberry_django.filter_field()
