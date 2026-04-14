from django.utils.translation import gettext as _
from rest_framework import serializers

from netbox.api.serializers import PrimaryModelSerializer
from tenancy.api.serializers_.tenants import TenantSerializer

from netbox_dns.models import DNSSECKeyTemplate

from ..nested_serializers import NestedDNSSECPolicySerializer
from ..field_serializers import TimePeriodField

__all__ = ("DNSSECKeyTemplateSerializer",)


class DNSSECKeyTemplateSerializer(PrimaryModelSerializer):
    class Meta:
        model = DNSSECKeyTemplate

        fields = (
            "id",
            "url",
            "display",
            "display_url",
            "name",
            "description",
            "comments",
            "tags",
            "policies",
            "type",
            "lifetime",
            "algorithm",
            "key_size",
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
            "type",
            "lifetime",
            "algorithm",
            "key_size",
            "description",
        )

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dns-api:dnsseckeytemplate-detail"
    )
    lifetime = TimePeriodField(
        required=False,
        allow_null=True,
    )
    policies = NestedDNSSECPolicySerializer(
        many=True,
        read_only=True,
        required=False,
        help_text=_("Policies using this Key Template"),
    )
    tenant = TenantSerializer(
        nested=True,
        required=False,
        allow_null=True,
    )
