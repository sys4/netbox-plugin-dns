from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry.scalars import ID
from strawberry_django import FilterLookup

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    from strawberry_django import FilterLookup as StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from netbox.graphql.filter_lookups import IntegerLookup
    from .enums import NetBoxDNSZoneStatusEnum
    from .view import NetBoxDNSViewFilter
    from .nameserver import NetBoxDNSNameServerFilter
    from .registrar import NetBoxDNSRegistrarFilter
    from .registration_contact import NetBoxDNSRegistrationContactFilter
    from .dnssec_policy import NetBoxDNSDNSSECPolicyFilter

from netbox_dns.models import Zone

__all__ = ("NetBoxDNSZoneFilter",)


@strawberry_django.filter_type(Zone, lookups=True)
class NetBoxDNSZoneFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    view: (
        Annotated["NetBoxDNSViewFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
    view_id: ID | None = strawberry_django.filter_field()
    nameservers: (
        Annotated[
            "NetBoxDNSNameServerFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    status: (
        Annotated[
            "NetBoxDNSZoneStatusEnum", strawberry.lazy("netbox_dns.graphql.enums")
        ]
        | None
    ) = strawberry_django.filter_field()
    default_ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()

    soa_ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_mname: (
        Annotated[
            "NetBoxDNSNameServerFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    soa_mname_id: ID | None = strawberry_django.filter_field()
    soa_rname: StrFilterLookup[str] | None = strawberry_django.filter_field()
    soa_serial: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_refresh: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_retry: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_expire: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_minimum: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    soa_serial_auto: FilterLookup[bool] | None = strawberry_django.filter_field()

    dnssec_policy: (
        Annotated[
            "NetBoxDNSDNSSECPolicyFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    )

    registrar: (
        Annotated[
            "NetBoxDNSRegistrarFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    )
    registrar_id: ID | None = strawberry_django.filter_field()
    registry_domain_id: StrFilterLookup[str] | None = strawberry_django.filter_field()
    registrant: (
        Annotated[
            "NetBoxDNSRegistrationContactFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    )
    registrant_id: ID | None = strawberry_django.filter_field()
    admin_c: (
        Annotated[
            "NetBoxDNSRegistrationContactFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    )
    admin_c_id: ID | None = strawberry_django.filter_field()
    tech_c: (
        Annotated[
            "NetBoxDNSRegistrationContactFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    )
    tech_c_id: ID | None = strawberry_django.filter_field()
    billing_c: (
        Annotated[
            "NetBoxDNSRegistrationContactFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    )
    billing_c_id: ID | None = strawberry_django.filter_field()

    rfc2317_prefix: StrFilterLookup[str] | None = strawberry_django.filter_field()
    rfc2317_parent_zone: (
        Annotated["NetBoxDNSZoneFilter", strawberry.lazy("netbox_dns.graphql.filters")]
        | None
    ) = strawberry_django.filter_field()
    rfc2317_parent_zone_id: ID | None = strawberry_django.filter_field()
    rfc2317_parent_managed: FilterLookup[bool] | None = strawberry_django.filter_field()

    arpa_network: StrFilterLookup[str] | None = strawberry_django.filter_field()
    active: FilterLookup[bool] | None = strawberry_django.filter_field()
