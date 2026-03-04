from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry.scalars import ID
from strawberry_django import StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from netbox.graphql.filter_lookups import IntegerLookup
    from .enums import (
        NetBoxDNSDNSSECKeyTemplateTypeEnum,
        NetBoxDNSDNSSECKeyTemplateAlgorithmEnum,
        NetBoxDNSDNSSECKeyTemplateKeySizeEnum,
    )
    from .dnssec_policy import NetBoxDNSDNSSECPolicyFilter

from netbox_dns.models import DNSSECKeyTemplate

__all__ = ("NetBoxDNSDNSSECKeyTemplateFilter",)


@strawberry_django.filter_type(DNSSECKeyTemplate, lookups=True)
class NetBoxDNSDNSSECKeyTemplateFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    type: (
        Annotated[
            "NetBoxDNSDNSSECKeyTemplateTypeEnum",
            strawberry.lazy("netbox_dns.graphql.enums"),
        ]
        | None
    ) = strawberry_django.filter_field()
    algorithm: (
        Annotated[
            "NetBoxDNSDNSSECKeyTemplateAlgorithmEnum",
            strawberry.lazy("netbox_dns.graphql.enums"),
        ]
        | None
    ) = strawberry_django.filter_field()
    lifetime: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    key_size: (
        Annotated[
            "NetBoxDNSDNSSECKeyTemplateKeySizeEnum",
            strawberry.lazy("netbox_dns.graphql.enums"),
        ]
        | None
    ) = strawberry_django.filter_field()
    policy: (
        Annotated[
            "NetBoxDNSDNSSECPolicyFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    policy_id: ID | None = strawberry_django.filter_field()
