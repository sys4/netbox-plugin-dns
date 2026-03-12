import ipaddress
import netaddr

import dns
from dns import name as dns_name
from dns import rdata

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, ExpressionWrapper, BooleanField, Min
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator

from netbox.models import PrimaryModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search
from netbox.plugins.utils import get_plugin_config
from utilities.querysets import RestrictedQuerySet

from netbox_dns.fields import AddressField
from netbox_dns.utilities import (
    arpa_to_prefix,
    name_to_unicode,
    check_filter,
    get_cidr_address,
)
from netbox_dns.validators import validate_generic_name, validate_record_value
from netbox_dns.mixins import ObjectModificationMixin
from netbox_dns.choices import (
    RecordTypeChoices,
    RecordStatusChoices,
    RecordClassChoices,
)

__all__ = (
    "Record",
    "RecordIndex",
)

ZONE_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "zone_active_status")
RECORD_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "record_active_status")


def min_ttl(*ttl_list):
    return min((ttl for ttl in ttl_list if ttl is not None), default=None)


def record_data_from_ip_address(ip_address, zone):
    cf_data = ip_address.custom_field_data

    if cf_data.get("ipaddress_dns_disabled"):
        # +
        # DNS record creation disabled for this address
        # -
        return None

    if zone.view.ip_address_filter is not None and not check_filter(
        ip_address, zone.view.ip_address_filter
    ):
        return None

    address = get_cidr_address(ip_address)

    data = {
        "name": (
            dns_name.from_text(ip_address.dns_name)
            .relativize(dns_name.from_text(zone.name))
            .to_text()
        ),
        "type": (
            RecordTypeChoices.A if address.version == 4 else RecordTypeChoices.AAAA
        ),
        "value": str(address.ip),
        "status": (
            RecordStatusChoices.STATUS_ACTIVE
            if ip_address.status
            in settings.PLUGINS_CONFIG["netbox_dns"].get(
                "dnssync_ipaddress_active_status", []
            )
            else RecordStatusChoices.STATUS_INACTIVE
        ),
    }

    if "ipaddress_dns_record_ttl" in cf_data:
        data["ttl"] = cf_data.get("ipaddress_dns_record_ttl")

    if (disable_ptr := cf_data.get("ipaddress_dns_record_disable_ptr")) is not None:
        data["disable_ptr"] = disable_ptr

    return data


class RecordManager(models.Manager.from_queryset(RestrictedQuerySet)):
    """
    Custom manager for records providing the activity status annotation
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                active=ExpressionWrapper(
                    Q(
                        zone__status__in=ZONE_ACTIVE_STATUS_LIST,
                        status__in=RECORD_ACTIVE_STATUS_LIST,
                    ),
                    output_field=BooleanField(),
                )
            )
        )


class Record(ObjectModificationMixin, ContactsMixin, PrimaryModel):
    class Meta:
        verbose_name = _("Record")
        verbose_name_plural = _("Records")

        ordering = (
            "fqdn",
            "zone",
            "name",
            "type",
            "value",
            "status",
        )

    objects = RecordManager()
    raw_objects = RestrictedQuerySet.as_manager()

    clone_fields = (
        "zone",
        "type",
        "name",
        "value",
        "status",
        "ttl",
        "disable_ptr",
        "description",
        "tenant",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cleanup_ptr_record = None

    def __str__(self):
        try:
            fqdn = dns_name.from_text(
                self.name, origin=dns_name.from_text(self.zone.name)
            ).relativize(dns_name.root)
            name = fqdn.to_unicode()
        except dns_name.IDNAException:
            name = fqdn.to_text()
        except dns_name.LabelTooLong:
            name = f"{self.name[:59]}..."

        return f"{name} [{self.type}]"

    unique_ptr_qs = Q(
        Q(disable_ptr=False),
        Q(Q(type=RecordTypeChoices.A) | Q(type=RecordTypeChoices.AAAA)),
    )

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        db_collation="natural_sort",
    )
    zone = models.ForeignKey(
        verbose_name=_("Zone"),
        to="Zone",
        on_delete=models.CASCADE,
        related_name="records",
    )
    fqdn = models.CharField(
        verbose_name=_("FQDN"),
        max_length=255,
        null=True,
        blank=True,
        default=None,
        db_collation="natural_sort",
    )
    type = models.CharField(
        verbose_name=_("Type"),
        choices=RecordTypeChoices,
        max_length=10,
    )
    value = models.CharField(
        verbose_name=_("Value"),
        max_length=65535,
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=50,
        choices=RecordStatusChoices,
        default=RecordStatusChoices.STATUS_ACTIVE,
        blank=False,
    )
    ttl = models.PositiveIntegerField(
        verbose_name=_("TTL"),
        null=True,
        blank=True,
        validators=[MaxValueValidator(2147483647)],
    )
    managed = models.BooleanField(
        verbose_name=_("Managed"),
        null=False,
        default=False,
    )
    ptr_record = models.ForeignKey(
        verbose_name=_("PTR Record"),
        to="self",
        on_delete=models.SET_NULL,
        related_name="address_records",
        null=True,
        blank=True,
    )
    disable_ptr = models.BooleanField(
        verbose_name=_("Disable PTR"),
        help_text=_("Disable PTR record creation"),
        default=False,
    )
    tenant = models.ForeignKey(
        verbose_name=_("Tenant"),
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="netbox_dns_records",
        blank=True,
        null=True,
    )
    ip_address = AddressField(
        verbose_name=_("Related IP Address"),
        help_text=_("IP address related to an address (A/AAAA) or PTR record"),
        blank=True,
        null=True,
    )
    ipam_ip_address = models.ForeignKey(
        verbose_name=_("IPAM IP Address"),
        to="ipam.IPAddress",
        on_delete=models.SET_NULL,
        related_name="netbox_dns_records",
        blank=True,
        null=True,
    )
    rfc2317_cname_record = models.ForeignKey(
        verbose_name=_("RFC2317 CNAME Record"),
        to="self",
        on_delete=models.SET_NULL,
        related_name="rfc2317_ptr_records",
        null=True,
        blank=True,
    )

    @property
    def cleanup_ptr_record(self):
        return self._cleanup_ptr_record

    @cleanup_ptr_record.setter
    def cleanup_ptr_record(self, ptr_record):
        self._cleanup_ptr_record = ptr_record

    @property
    def display_name(self):
        return name_to_unicode(self.name)

    def get_status_color(self):
        return RecordStatusChoices.colors.get(self.status)

    @property
    def value_fqdn(self):
        if self.type not in (RecordTypeChoices.CNAME, RecordTypeChoices.NS):
            return None

        _zone = dns_name.from_text(self.zone.name)
        value_fqdn = dns_name.from_text(self.value, origin=_zone)

        return value_fqdn.to_text()

    @property
    def address_from_name(self):
        prefix = arpa_to_prefix(self.fqdn)
        if prefix is not None:
            return prefix.ip

        return None

    @property
    def address_from_rfc2317_name(self):
        prefix = self.zone.rfc2317_prefix
        if prefix is not None:
            return ".".join(str(prefix.ip).split(".")[0:3] + [self.name])

        return None

    @property
    def is_active(self):
        return (
            self.status in RECORD_ACTIVE_STATUS_LIST
            and self.zone.status in ZONE_ACTIVE_STATUS_LIST
        )

    @property
    def is_address_record(self):
        return self.type in (RecordTypeChoices.A, RecordTypeChoices.AAAA)

    @property
    def is_ptr_record(self):
        return self.type == RecordTypeChoices.PTR

    @property
    def rfc2317_ptr_name(self):
        return self.value.split(".")[-1]

    @property
    def rfc2317_ptr_cname_name(self):
        assert self.type == RecordTypeChoices.A
        if (
            self.ptr_record is not None
            and self.ptr_record.zone.rfc2317_parent_zone is not None
        ):
            return dns_name.from_text(
                ipaddress.ip_address(self.value).reverse_pointer
            ).relativize(
                dns_name.from_text(self.ptr_record.zone.rfc2317_parent_zone.name)
            )

        return None

    @property
    def ptr_zone(self):
        if self.type == RecordTypeChoices.A:
            ptr_zone = (
                self.zone.view.zones.filter(
                    rfc2317_prefix__net_contains=self.value,
                )
                .order_by("rfc2317_prefix__net_mask_length")
                .last()
            )

            if ptr_zone is not None:
                return ptr_zone

        ptr_zone = (
            self.zone.view.zones.filter(arpa_network__net_contains=self.value)
            .order_by("arpa_network__net_mask_length")
            .last()
        )

        return ptr_zone

    @property
    def is_delegation_record(self):
        return self in self.zone.delegation_records

    def check_zone_cut_conflict(self):
        record_name = dns_name.from_text(self.fqdn)

        for zone in self.zone.descendant_zones:
            zone_name = dns_name.from_text(zone.fqdn)

            if not record_name.is_subdomain(zone_name):
                continue

            if (
                self.type
                in (
                    RecordTypeChoices.NS,
                    RecordTypeChoices.DS,
                )
                and record_name == zone_name
            ):
                continue

            if self.type in (
                RecordTypeChoices.A,
                RecordTypeChoices.AAAA,
            ) and record_name in (
                dns_name.from_text(nameserver.name)
                for nameserver in zone.nameservers.all()
            ):
                continue

            raise ValidationError(
                _("{fqdn} is masked by child zone {zone}").format(
                    fqdn=self.fqdn.rstrip("."), zone=zone.name
                )
            )

    def refresh_ptr_record(
        self, ptr_record=None, update_rfc2317_cname=True, save_zone_serial=True
    ):
        if ptr_record is None:
            return

        if not ptr_record.address_records.exists():
            if ptr_record.rfc2317_cname_record is not None:
                ptr_record.remove_from_rfc2317_cname_record()

            ptr_record.delete(save_zone_serial=save_zone_serial)

        elif update_rfc2317_cname:
            ptr_record.update_rfc2317_cname_record(save_zone_serial=save_zone_serial)

    def update_ptr_record(self, update_rfc2317_cname=True, save_zone_serial=True):
        ptr_zone = self.ptr_zone

        # +
        # Check whether a PTR record is optioned for and return if that is not the
        # case.
        # -
        if (
            ptr_zone is None
            or self.disable_ptr
            or not self.is_active
            or self.name.startswith("*")
        ):
            self.cleanup_ptr_record = self.ptr_record
            self.ptr_record = None
            return

        # +
        # Determine the ptr_name and ptr_value related to the ptr_zone. RFC2317
        # PTR names and zones need to be handled differently.
        # -
        if ptr_zone.is_rfc2317_zone:
            ptr_name = self.rfc2317_ptr_name
        else:
            ptr_name = (
                dns_name.from_text(ipaddress.ip_address(self.value).reverse_pointer)
                .relativize(dns_name.from_text(ptr_zone.name))
                .to_text()
            )
        ptr_value = self.fqdn

        # +
        # If there is an existing and matching PTR record there is nothing to be done.
        # -
        if (ptr_record := self.ptr_record) is not None:
            if (
                ptr_record.zone == ptr_zone
                and ptr_record.name == ptr_name
                and ptr_record.value == ptr_value
                and ptr_record.ttl == self.ttl
            ):
                return

            # +
            # If the existing PTR record no longer matches the address record,
            # check whether there is an existing PTR record that does. In that
            # case, mark the old PTR record for cleanup and use the existing one.
            # -
            try:
                existing_ptr_record = Record.objects.get(
                    name=ptr_name,
                    zone=ptr_zone,
                    type=RecordTypeChoices.PTR,
                    value=ptr_value,
                )

                self.cleanup_ptr_record = self.ptr_record
                self.ptr_record = existing_ptr_record
                ptr_record = self.ptr_record

            except Record.DoesNotExist:
                pass

            # +
            # If there is an RFC2317 CNAME for the PTR record and it is either
            # not required or needs to be changed, remove it.
            # -
            if (
                ptr_record.zone.pk != ptr_zone.pk or not ptr_record.zone.is_rfc2317_zone
            ) and ptr_record.rfc2317_cname_record is not None:
                ptr_record.rfc2317_cname_record.delete(
                    save_zone_serial=save_zone_serial
                )
                ptr_record.rfc2317_cname_record = None

            # +
            # If the PTR record is used exclusively by the address record it can be
            # modified to match the new name, zone, value and TTL.
            # -
            if ptr_record.address_records.count() == 1:
                ptr_record.snapshot()
                ptr_record.zone = ptr_zone
                ptr_record.name = ptr_name
                ptr_record.value = ptr_value
                ptr_record.ttl = self.ttl
                ptr_record.managed = True
                ptr_record.save(
                    update_rfc2317_cname=update_rfc2317_cname,
                    save_zone_serial=save_zone_serial,
                )
                return

        # +
        # Either there was no PTR record or the existing PTR record could not be re-used,
        # so we need to either find a matching PTR record or create a new one.
        # -
        try:
            ptr_record = Record.objects.get(
                name=ptr_name,
                zone=ptr_zone,
                type=RecordTypeChoices.PTR,
                value=ptr_value,
            )

        # +
        # If no existing PTR record could be found in the database, create a new
        # one from scratch.
        # -
        except Record.DoesNotExist:
            ptr_record = Record(
                zone_id=ptr_zone.pk,
                type=RecordTypeChoices.PTR,
                name=ptr_name,
                ttl=self.ttl,
                value=ptr_value,
                managed=True,
            )
            ptr_record.save(
                update_rfc2317_cname=update_rfc2317_cname,
                save_zone_serial=save_zone_serial,
            )

        self.ptr_record = ptr_record

    update_ptr_record.alters_data = True

    def remove_from_rfc2317_cname_record(self, save_zone_serial=True):
        if self.rfc2317_cname_record.pk:
            rfc2317_ptr_records = self.rfc2317_cname_record.rfc2317_ptr_records.exclude(
                pk=self.pk
            )

            if rfc2317_ptr_records:
                self.rfc2317_cname_record.ttl = rfc2317_ptr_records.aggregate(
                    Min("ttl")
                ).get("ttl__min")
                self.rfc2317_cname_record.save(
                    update_fields=["ttl"], save_zone_serial=save_zone_serial
                )
            else:
                self.rfc2317_cname_record.delete()

    remove_from_rfc2317_cname_record.alters_data = True

    def update_rfc2317_cname_record(self, save_zone_serial=True):
        if self.zone.rfc2317_parent_managed:
            cname_name = (
                dns_name.from_text(
                    ipaddress.ip_address(self.ip_address).reverse_pointer
                )
                .relativize(dns_name.from_text(self.zone.rfc2317_parent_zone.name))
                .to_text()
            )

            if self.rfc2317_cname_record is not None:
                if self.rfc2317_cname_record.name == cname_name:
                    self.rfc2317_cname_record.zone = self.zone.rfc2317_parent_zone
                    self.rfc2317_cname_record.value = self.fqdn
                    self.rfc2317_cname_record.ttl = min_ttl(
                        self.rfc2317_cname_record.rfc2317_ptr_records.exclude(
                            pk=self.pk
                        )
                        .aggregate(Min("ttl"))
                        .get("ttl__min"),
                        self.ttl,
                    )
                    self.rfc2317_cname_record.save(save_zone_serial=save_zone_serial)

                    return

                self.remove_from_rfc2317_cname_record(save_zone_serial=save_zone_serial)

            rfc2317_cname_record = self.zone.rfc2317_parent_zone.records.filter(
                name=cname_name,
                type=RecordTypeChoices.CNAME,
                managed=True,
                value=self.fqdn,
            ).first()

            if rfc2317_cname_record is not None:
                rfc2317_cname_record.ttl = min_ttl(
                    rfc2317_cname_record.rfc2317_ptr_records.exclude(pk=self.pk)
                    .aggregate(Min("ttl"))
                    .get("ttl__min"),
                    self.ttl,
                )
                rfc2317_cname_record.save(
                    update_fields=["ttl"], save_zone_serial=save_zone_serial
                )

            else:
                rfc2317_cname_record = Record(
                    name=cname_name,
                    type=RecordTypeChoices.CNAME,
                    zone=self.zone.rfc2317_parent_zone,
                    managed=True,
                    value=self.fqdn,
                    ttl=self.ttl,
                )
                rfc2317_cname_record.save(save_zone_serial=save_zone_serial)

            self.rfc2317_cname_record = rfc2317_cname_record

        else:
            if self.rfc2317_cname_record is not None:
                self.rfc2317_cname_record.delete(save_zone_serial=save_zone_serial)
                self.rfc2317_cname_record = None

    update_rfc2317_cname_record.alters_data = True

    def update_from_ip_address(self, ip_address, zone=None):
        """
        Update an address record according to data from an IPAddress object.

        Returns a tuple of two booleans: (update, delete).

        update: The record was updated and needs to be cleaned and/or saved
        delete: The record is no longer needed and needs to be deleted
        """
        if zone is None:
            zone = self.zone

        data = record_data_from_ip_address(ip_address, zone)

        if data is None:
            return False, True

        if all((getattr(self, attr) == data[attr] for attr in data.keys())):
            return False, False

        for attr, value in data.items():
            setattr(self, attr, value)

        return True, False

    update_from_ip_address.alters_data = True

    @classmethod
    def create_from_ip_address(cls, ip_address, zone):
        data = record_data_from_ip_address(ip_address, zone)

        if data is None:
            return

        return Record(
            zone=zone,
            managed=True,
            ipam_ip_address=ip_address,
            **data,
        )

    create_from_ip_address.alters_data = True

    def update_fqdn(self, zone=None):
        if zone is None:
            zone = self.zone

        _zone = dns_name.from_text(zone.name, origin=dns_name.root)
        name = dns_name.from_text(self.name, origin=None)
        fqdn = dns_name.from_text(self.name, origin=_zone)

        if not fqdn.is_subdomain(_zone):
            raise ValidationError(
                {
                    "name": _("{name} is not a name in {zone}").format(
                        name=self.name, zone=zone.name
                    ),
                }
            )

        _zone.to_unicode()
        name.to_unicode()

        self.name = name.relativize(_zone).to_text()
        self.fqdn = fqdn.to_text()

    update_fqdn.alters_data = True

    def validate_name(self, new_zone=None):
        if new_zone is None:
            new_zone = self.zone

        try:
            self.update_fqdn(zone=new_zone)

        except dns.exception.DNSException as exc:
            raise ValidationError(
                {
                    "name": str(exc),
                }
            )

        if self.type not in get_plugin_config(
            "netbox_dns", "tolerate_non_rfc1035_types", default=[]
        ):
            try:
                validate_generic_name(
                    self.name,
                    (
                        self.type
                        in get_plugin_config(
                            "netbox_dns",
                            "tolerate_leading_underscore_types",
                            default=[],
                        )
                    ),
                )
            except ValidationError as exc:
                raise ValidationError(
                    {
                        "name": exc,
                    }
                )

        if get_plugin_config("netbox_dns", "enforce_zone_cut_checking"):
            try:
                self.check_zone_cut_conflict()
            except ValidationError as exc:
                raise ValidationError({"name": exc})

    validate_name.alters_data = True

    def validate_value(self):
        try:
            validate_record_value(self)
        except ValidationError as exc:
            raise ValidationError({"value": exc})

    def check_unique_record(self, new_zone=None):
        if not get_plugin_config("netbox_dns", "enforce_unique_records", False):
            return

        if not self.is_active:
            return

        if new_zone is None:
            new_zone = self.zone

        records = new_zone.records.filter(
            name__iexact=self.name,
            type=self.type,
            value=self.value,
            status__in=RECORD_ACTIVE_STATUS_LIST,
        )

        if not self._state.adding:
            records = records.exclude(pk=self.pk)

        if records.exists():
            if self.ipam_ip_address is not None:
                if not records.filter(
                    ipam_ip_address__isnull=True
                ).exists() or get_plugin_config(
                    "netbox_dns", "dnssync_conflict_deactivate", False
                ):
                    return

            raise ValidationError(
                {
                    "value": _(
                        "There is already an active {type} record for name {name} in zone {zone} with value {value}."
                    ).format(
                        type=self.type, name=self.name, zone=self.zone, value=self.value
                    )
                }
            )

    @property
    def absolute_value(self):
        if self.type in RecordTypeChoices.CUSTOM_TYPES:
            return self.value

        zone = dns_name.from_text(self.zone.name)
        rr = rdata.from_text(RecordClassChoices.IN, self.type, self.value)

        match self.type:
            case (
                RecordTypeChoices.CNAME
                | RecordTypeChoices.DNAME
                | RecordTypeChoices.NS
                | RecordTypeChoices.HTTPS
                | RecordTypeChoices.SRV
                | RecordTypeChoices.SVCB
            ):
                return rr.replace(target=rr.target.derelativize(zone)).to_text()

            case RecordTypeChoices.MX | RecordTypeChoices.RT | RecordTypeChoices.KX:
                return rr.replace(exchange=rr.exchange.derelativize(zone)).to_text()

            case RecordTypeChoices.RP:
                return rr.replace(
                    mbox=rr.mbox.derelativize(zone), txt=rr.txt.derelativize(zone)
                ).to_text()

            case RecordTypeChoices.NAPTR:
                return rr.replace(
                    replacement=rr.replacement.derelativize(zone)
                ).to_text()

            case RecordTypeChoices.PX:
                return rr.replace(
                    map822=rr.map822.derelativize(zone),
                    mapx400=rr.mapx400.derelativize(zone),
                ).to_text()

        return self.value

    def handle_conflicting_address_records(self):
        if self.ipam_ip_address is None or not self.is_active:
            return

        if not get_plugin_config("netbox_dns", "dnssync_conflict_deactivate", False):
            return

        records = self.zone.records.filter(
            name=self.name,
            type=self.type,
            value=self.value,
            status__in=RECORD_ACTIVE_STATUS_LIST,
            ipam_ip_address__isnull=True,
        )

        for record in records:
            record.status = RecordStatusChoices.STATUS_INACTIVE
            record.save(update_fields=["status"])

    handle_conflicting_address_records.alters_data = True

    def check_unique_rrset_ttl(self):
        if not self._state.adding:
            return

        if not get_plugin_config("netbox_dns", "enforce_unique_rrset_ttl", False):
            return

        if self.ipam_ip_address is not None and get_plugin_config(
            "netbox_dns", "dnssync_conflict_deactivate", False
        ):
            return

        if self.type == RecordTypeChoices.PTR and self.managed:
            return

        records = (
            self.zone.records.filter(
                name=self.name,
                type=self.type,
            )
            .exclude(ttl=self.ttl)
            .exclude(type=RecordTypeChoices.PTR, managed=True)
            .exclude(status=RecordStatusChoices.STATUS_INACTIVE)
        )

        if self.ipam_ip_address is not None:
            records = records.exclude(ipam_ip_address__isnull=False)

        if not records.exists():
            return

        conflicting_ttls = {record.ttl for record in records}
        if len(conflicting_ttls) == 1 and self.ttl is None:
            self.ttl = conflicting_ttls.pop()
            return

        raise ValidationError(
            {
                "ttl": _(
                    "There is at least one active {type} record for name {name} in zone {zone} and TTL is different ({ttls})."
                ).format(
                    type=self.type,
                    name=self.name,
                    zone=self.zone,
                    ttls=", ".join(str(ttl) for ttl in conflicting_ttls),
                )
            }
        )

    check_unique_rrset_ttl.alters_data = True

    def update_rrset_ttl(self, ttl=None):
        if self._state.adding:
            return

        if not get_plugin_config("netbox_dns", "enforce_unique_rrset_ttl", False):
            return

        if self.type == RecordTypeChoices.PTR and self.managed:
            return

        if ttl is None:
            ttl = self.ttl

        records = (
            self.zone.records.filter(
                name=self.name,
                type=self.type,
            )
            .exclude(pk=self.pk)
            .exclude(ttl=ttl)
            .exclude(type=RecordTypeChoices.PTR, managed=True)
            .exclude(status=RecordStatusChoices.STATUS_INACTIVE)
        )

        for record in records:
            record.ttl = ttl
            record.save(update_fields=["ttl"], update_rrset_ttl=False)

    update_rrset_ttl.alters_data = True

    def clean_fields(self, exclude=None):
        self.type = self.type.upper()
        if get_plugin_config("netbox_dns", "convert_names_to_lowercase", False):
            self.name = self.name.lower()

        super().clean_fields(exclude=exclude)

    clean_fields.alters_data = True

    def clean(self, *args, new_zone=None, **kwargs):
        self.validate_name(new_zone=new_zone)
        self.validate_value()
        self.check_unique_record(new_zone=new_zone)
        if self._state.adding:
            self.check_unique_rrset_ttl()

        if not self.is_address_record:
            self.disable_ptr = False

        if not self.is_active:
            return

        records = self.zone.records.filter(name=self.name, active=True).exclude(
            pk=self.pk
        )

        if self.type == RecordTypeChoices.A and not self.disable_ptr:
            ptr_zone = self.ptr_zone

            if (
                ptr_zone is not None
                and ptr_zone.is_rfc2317_zone
                and ptr_zone.rfc2317_parent_managed
            ):
                ptr_cname_zone = ptr_zone.rfc2317_parent_zone
                ptr_cname_name = self.rfc2317_ptr_cname_name
                ptr_fqdn = dns_name.from_text(
                    self.rfc2317_ptr_name, origin=dns_name.from_text(ptr_zone.name)
                )

                if (
                    ptr_cname_zone.records.filter(
                        name=ptr_cname_name,
                        active=True,
                    )
                    .exclude(
                        type=RecordTypeChoices.CNAME,
                        value=ptr_fqdn,
                    )
                    .exclude(type=RecordTypeChoices.NSEC)
                    .exists()
                ):
                    raise ValidationError(
                        {
                            "value": _(
                                "There is already an active record for name {name} in zone {zone}, RFC2317 CNAME is not allowed."
                            ).format(name=ptr_cname_name, zone=ptr_cname_zone)
                        }
                    )

        if self.type == RecordTypeChoices.SOA and self.name != "@":
            raise ValidationError(
                {
                    "name": _(
                        "SOA records are only allowed with name @ and are created automatically by NetBox DNS"
                    )
                }
            )

        if self.type == RecordTypeChoices.CNAME:
            if records.exclude(type=RecordTypeChoices.NSEC).exists():
                raise ValidationError(
                    {
                        "type": _(
                            "There is already an active record for name {name} in zone {zone}, CNAME is not allowed."
                        ).format(name=self.name, zone=self.zone)
                    }
                )

        elif (
            records.filter(type=RecordTypeChoices.CNAME).exists()
            and self.type != RecordTypeChoices.NSEC
        ):
            raise ValidationError(
                {
                    "type": _(
                        "There is already an active CNAME record for name {name} in zone {zone}, no other record allowed."
                    ).format(name=self.name, zone=self.zone)
                }
            )

        elif self.type in RecordTypeChoices.SINGLETONS:
            if records.filter(type=self.type).exists():
                raise ValidationError(
                    {
                        "type": _(
                            "There is already an active {type} record for name {name} in zone {zone}, more than one are not allowed."
                        ).format(type=self.type, name=self.name, zone=self.zone)
                    }
                )

        super().clean(*args, **kwargs)

    clean.alters_data = True

    def save(
        self,
        *args,
        update_rfc2317_cname=True,
        save_zone_serial=True,
        update_rrset_ttl=True,
        **kwargs,
    ):
        self.full_clean()

        if not self._state.adding and update_rrset_ttl:
            self.update_rrset_ttl()

        if self.is_ptr_record:
            if self.zone.is_rfc2317_zone:
                self.ip_address = self.address_from_rfc2317_name
                if update_rfc2317_cname:
                    self.update_rfc2317_cname_record(save_zone_serial=save_zone_serial)
            else:
                self.ip_address = self.address_from_name

        elif self.is_address_record:
            self.ip_address = netaddr.IPAddress(self.value)
        else:
            self.ip_address = None

        if self.is_address_record:
            self.handle_conflicting_address_records()
            self.update_ptr_record(
                update_rfc2317_cname=update_rfc2317_cname,
                save_zone_serial=save_zone_serial,
            )
        elif self.ptr_record is not None:
            self.cleanup_ptr_record = self.ptr_record
            self.ptr_record = None

        changed_fields = self.changed_fields
        if changed_fields is None or changed_fields:
            super().save(*args, **kwargs)

            self.refresh_ptr_record(
                self.cleanup_ptr_record,
                update_rfc2317_cname=update_rfc2317_cname,
                save_zone_serial=save_zone_serial,
            )

            if self.type != RecordTypeChoices.SOA and self.zone.soa_serial_auto:
                self.zone.update_serial(save_zone_serial=save_zone_serial)

    def delete(self, *args, save_zone_serial=True, **kwargs):
        if self.rfc2317_cname_record:
            self.remove_from_rfc2317_cname_record(save_zone_serial=save_zone_serial)

        ptr_record = self.ptr_record

        super().delete(*args, **kwargs)

        self.refresh_ptr_record(
            ptr_record,
            update_rfc2317_cname=True,
            save_zone_serial=save_zone_serial,
        )

        _zone = self.zone
        if _zone.soa_serial_auto:
            _zone.update_serial(save_zone_serial=save_zone_serial)


@register_search
class RecordIndex(SearchIndex):
    model = Record

    fields = (
        ("fqdn", 100),
        ("name", 120),
        ("value", 150),
        ("zone", 200),
        ("type", 200),
        ("description", 500),
    )
