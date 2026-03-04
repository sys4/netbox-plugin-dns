from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry_django import FilterLookup, StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from netbox.graphql.filter_lookups import IntegerLookup
    from .enums import (
        NetBoxDNSRecordStatusEnum,
        NetBoxDNSRecordTypeEnum,
    )

from netbox_dns.models import RecordTemplate

__all__ = ("NetBoxDNSRecordTemplateFilter",)


@strawberry_django.filter_type(RecordTemplate, lookups=True)
class NetBoxDNSRecordTemplateFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    record_name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    type: (
        Annotated[
            "NetBoxDNSRecordTypeEnum", strawberry.lazy("netbox_dns.graphql.enums")
        ]
        | None
    ) = strawberry_django.filter_field()
    status: (
        Annotated[
            "NetBoxDNSRecordStatusEnum", strawberry.lazy("netbox_dns.graphql.enums")
        ]
        | None
    ) = strawberry_django.filter_field()
    ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    value: StrFilterLookup[str] | None = strawberry_django.filter_field()
    disable_ptr: FilterLookup[bool] | None = strawberry_django.filter_field()

    zone_templates: (
        Annotated[
            "NetBoxDNSRecordTemplateFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
