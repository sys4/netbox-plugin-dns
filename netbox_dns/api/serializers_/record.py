from django.utils.translation import gettext as _
from rest_framework import serializers

from ipam.api.serializers import IPAddressSerializer
from netbox.api.serializers import PrimaryModelSerializer
from netbox_dns.models import Record
from tenancy.api.serializers import TenantSerializer

from ..field_serializers import TimePeriodField
from ..nested_serializers import NestedRecordSerializer, NestedZoneSerializer

__all__ = ("RecordSerializer",)


class RecordSerializer(PrimaryModelSerializer):
    class Meta:
        model = Record
        fields = (
            "id",
            "url",
            "zone",
            "display",
            "display_url",
            "type",
            "name",
            "description",
            "comments",
            "tags",
            "fqdn",
            "value",
            "status",
            "ttl",
            "created",
            "last_updated",
            "managed",
            "disable_ptr",
            "ptr_record",
            "address_records",
            "active",
            "custom_fields",
            "tenant",
            "ipam_ip_address",
            "absolute_value",
            "expiration_date",
            "expired",
            "owner",
        )

        brief_fields = (
            "id",
            "url",
            "zone",
            "display",
            "type",
            "name",
            "fqdn",
            "value",
            "status",
            "ttl",
            "description",
            "managed",
            "active",
            "expired",
        )

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_dns-api:record-detail"
    )
    ttl = TimePeriodField(
        required=False,
        allow_null=True,
    )
    ptr_record = NestedRecordSerializer(
        many=False,
        read_only=True,
        required=False,
        allow_null=True,
        help_text=_("PTR record related to an address"),
    )
    address_records = NestedRecordSerializer(
        many=True,
        read_only=True,
        required=False,
        allow_null=True,
        help_text=_("Address records related to the PTR"),
    )
    zone = NestedZoneSerializer(
        many=False,
        required=False,
        help_text=_("Zone the record belongs to"),
    )
    active = serializers.BooleanField(
        required=False,
        read_only=True,
    )
    ipam_ip_address = IPAddressSerializer(
        nested=True,
        many=False,
        read_only=True,
        required=False,
        allow_null=True,
        help_text=_("IPAddress linked to the record"),
    )
    tenant = TenantSerializer(
        nested=True,
        required=False,
        allow_null=True,
    )
    expired = serializers.SerializerMethodField()

    def get_expired(self, instance):
        return instance.is_expired

    def validate(self, data):
        if self.instance is not None and self.instance.managed:
            raise serializers.ValidationError(
                _("{object} is managed, refusing update").format(object=self.instance)
            )
        if isinstance(data, dict) and data.get("managed"):
            raise serializers.ValidationError(
                _("'managed' is True, refusing to create or update a managed record")
            )

        return super().validate(data)
