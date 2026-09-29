from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _
from rest_framework import serializers

from ipam.api.serializers import PrefixSerializer
from netbox.api.serializers import PrimaryModelSerializer
from netbox_dns.models import View
from netbox_dns.utilities import validate_ip_address_filter
from tenancy.api.serializers import TenantSerializer

__all__ = ("ViewSerializer",)


class ViewSerializer(PrimaryModelSerializer):
    class Meta:
        model = View

        fields = (
            "id",
            "url",
            "display",
            "display_url",
            "name",
            "description",
            "comments",
            "tags",
            "default_view",
            "created",
            "last_updated",
            "custom_fields",
            "tenant",
            "prefixes",
            "ip_address_filter",
            "owner",
        )

        brief_fields = (
            "id",
            "url",
            "display",
            "name",
            "default_view",
            "description",
        )

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dns-api:view-detail"
    )
    default_view = serializers.BooleanField(
        read_only=True,
    )
    prefixes = PrefixSerializer(
        many=True,
        nested=True,
        read_only=False,
        required=False,
        help_text=_("IPAM Prefixes assigned to the View"),
    )
    tenant = TenantSerializer(
        nested=True,
        required=False,
        allow_null=True,
    )

    def validate_ip_address_filter(self, value):
        try:
            validate_ip_address_filter(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value

    def create(self, validated_data):
        prefixes = validated_data.pop("prefixes", None)

        view = super().create(validated_data)

        if prefixes is not None:
            view.prefixes.set(prefixes)

        return view

    def update(self, instance, validated_data):
        prefixes = validated_data.pop("prefixes", None)

        view = super().update(instance, validated_data)

        if prefixes is not None:
            view.prefixes.set(prefixes)

        return view
