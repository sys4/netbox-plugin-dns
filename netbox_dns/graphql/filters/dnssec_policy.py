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
    from netbox.graphql.filter_lookups import IntegerLookup
    from .enums import NetBoxDNSDNSSECPolicyStatusEnum
    from .dnssec_key_template import NetBoxDNSDNSSECKeyTemplateFilter
    from .zone import NetBoxDNSZoneFilter
    from .zone_template import NetBoxDNSZoneTemplateFilter

from netbox_dns.models import DNSSECPolicy
from netbox_dns.graphql.filter_lookups import PolicyDigestArrayLookup

__all__ = ("NetBoxDNSDNSSECPolicyFilter", "PolicyDigestArrayLookup")


@strawberry_django.filter_type(DNSSECPolicy, lookups=True)
class NetBoxDNSDNSSECPolicyFilter(
    ContactFilterMixin,
    TenancyFilterMixin,
    PrimaryModelFilter,
):
    name: StrFilterLookup[str] | None = strawberry_django.filter_field()
    status: (
        Annotated[
            "NetBoxDNSDNSSECPolicyStatusEnum",
            strawberry.lazy("netbox_dns.graphql.enums"),
        ]
        | None
    ) = strawberry_django.filter_field()
    inline_signing: FilterLookup[bool] | None = strawberry_django.filter_field()
    key_templates: (
        Annotated[
            "NetBoxDNSDNSSECKeyTemplateFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    zones: (
        Annotated[
            "NetBoxDNSZoneFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    zone_templates: (
        Annotated[
            "NetBoxDNSZoneTemplateFilter",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    dnskey_ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    purge_keys: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    publish_safety: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    retire_safety: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    signatures_jitter: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    signatures_refresh: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    signatures_validity: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    signatures_validity_dnskey: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    max_zone_ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    zone_propagation_delay: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    cds_digest_types: (
        Annotated[
            "PolicyDigestArrayLookup",
            strawberry.lazy("netbox_dns.graphql.filters"),
        ]
        | None
    ) = strawberry_django.filter_field()
    create_cdnskey: FilterLookup[bool] | None = strawberry_django.filter_field()
    parent_ds_ttl: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    parent_propagation_delay: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    use_nsec3: FilterLookup[bool] | None = strawberry_django.filter_field()
    nsec3_iterations: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
    nsec3_opt_out: FilterLookup[bool] | None = strawberry_django.filter_field()
    nsec3_salt_size: (
        Annotated["IntegerLookup", strawberry.lazy("netbox.graphql.filter_lookups")]
        | None
    ) = strawberry_django.filter_field()
