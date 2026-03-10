from typing import Annotated, TYPE_CHECKING

import strawberry
import strawberry_django
from strawberry.scalars import ID

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    from strawberry_django import FilterLookup as StrFilterLookup

from netbox.graphql.filters import PrimaryModelFilter
from tenancy.graphql.filter_mixins import ContactFilterMixin, TenancyFilterMixin

if TYPE_CHECKING:
    from .enums import NetBoxDNSZoneStatusEnum
    from .nameserver import NetBoxDNSNameServerFilter
    from .record_template import NetBoxDNSRecordTemplateFilter
    from .registrar import NetBoxDNSRegistrarFilter
    from .registration_contact import NetBoxDNSRegistrationContactFilter

from netbox_dns.models import ZoneTemplate

__all__ = ("NetBoxDNSZoneTemplateFilter",)


@strawberry_django.filter_type(ZoneTemplate, lookups=True)
class NetBoxDNSZoneTemplateFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
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

    soa_mname: (
        Annotated[
            "NetBoxDNSNameServerFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    ) = strawberry_django.filter_field()
    soa_mname_id: ID | None = strawberry_django.filter_field()
    soa_rname: StrFilterLookup[str] | None = strawberry_django.filter_field()

    registrar: (
        Annotated[
            "NetBoxDNSRegistrarFilter", strawberry.lazy("netbox_dns.graphql.filters")
        ]
        | None
    )
    registrar_id: ID | None = strawberry_django.filter_field()
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
    record_templates: (
        Annotated[
            "NetBoxDNSRecordTemplateFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
