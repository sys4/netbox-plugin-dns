from django.utils.translation import gettext as _
from rest_framework import serializers

from netbox.api.serializers import PrimaryModelSerializer
from tenancy.api.serializers_.tenants import TenantSerializer

from netbox_dns.models import DNSSECPolicy

from .dnssec_key_template import DNSSECKeyTemplateSerializer
from ..nested_serializers import NestedZoneSerializer, NestedZoneTemplateSerializer
from ..field_serializers import TimePeriodField

__all__ = ("DNSSECPolicySerializer",)


class DNSSECPolicySerializer(PrimaryModelSerializer):
    class Meta:
        model = DNSSECPolicy

        fields = (
            "id",
            "url",
            "display",
            "display_url",
            "name",
            "description",
            "comments",
            "tags",
            "status",
            "inline_signing",
            "key_templates",
            "zones",
            "zone_templates",
            "dnskey_ttl",
            "purge_keys",
            "publish_safety",
            "retire_safety",
            "signatures_jitter",
            "signatures_refresh",
            "signatures_validity",
            "signatures_validity_dnskey",
            "max_zone_ttl",
            "zone_propagation_delay",
            "create_cdnskey",
            "cds_digest_types",
            "parent_ds_ttl",
            "parent_propagation_delay",
            "use_nsec3",
            "nsec3_iterations",
            "nsec3_opt_out",
            "nsec3_salt_size",
            "created",
            "last_updated",
            "custom_fields",
            "tenant",
        )

        brief_fields = (
            "id",
            "url",
            "display",
            "name",
            "description",
            "status",
            "inline_signing",
        )

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dns-api:dnssecpolicy-detail"
    )
    key_templates = DNSSECKeyTemplateSerializer(
        nested=True,
        many=True,
        read_only=False,
        required=False,
        help_text=_("Key templates assigned to the policy"),
    )
    dnskey_ttl = TimePeriodField(
        required=False,
        allow_null=True,
    )
    purge_keys = TimePeriodField(
        required=False,
        allow_null=True,
    )
    publish_safety = TimePeriodField(
        required=False,
        allow_null=True,
    )
    retire_safety = TimePeriodField(
        required=False,
        allow_null=True,
    )
    signatures_jitter = TimePeriodField(
        required=False,
        allow_null=True,
    )
    signatures_refresh = TimePeriodField(
        required=False,
        allow_null=True,
    )
    signatures_validity = TimePeriodField(
        required=False,
        allow_null=True,
    )
    signatures_validity_dnskey = TimePeriodField(
        required=False,
        allow_null=True,
    )
    max_zone_ttl = TimePeriodField(
        required=False,
        allow_null=True,
    )
    zone_propagation_delay = TimePeriodField(
        required=False,
        allow_null=True,
    )
    parent_ds_ttl = TimePeriodField(
        required=False,
        allow_null=True,
    )
    parent_propagation_delay = TimePeriodField(
        required=False,
        allow_null=True,
    )
    zones = NestedZoneSerializer(
        many=True,
        read_only=True,
        required=False,
        help_text=_("Zones this policy is assigned to"),
    )
    zone_templates = NestedZoneTemplateSerializer(
        many=True,
        read_only=True,
        required=False,
        help_text=_("Zone templates this policy is assigned to"),
    )
    tenant = TenantSerializer(
        nested=True,
        required=False,
        allow_null=True,
    )

    def create(self, validated_data):
        dnssec_key_templates = validated_data.pop("key_templates", None)

        dnssec_policy = super().create(validated_data)

        if dnssec_key_templates is not None:
            dnssec_policy.key_templates.set(dnssec_key_templates)

        return dnssec_policy

    def update(self, instance, validated_data):
        dnssec_key_templates = validated_data.pop("key_templates", None)

        dnssec_policy = super().update(instance, validated_data)

        if dnssec_key_templates is not None:
            dnssec_policy.key_templates.set(dnssec_key_templates)

        return dnssec_policy
