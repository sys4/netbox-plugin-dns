import re
from math import ceil
from datetime import datetime, date

from dns import name as dns_name
from dns.exception import DNSException
from dns.rdtypes.ANY import SOA
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
)
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import Q, Max, ExpressionWrapper, BooleanField, UniqueConstraint
from django.db.models.functions import Length, Lower
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.models.features import ContactsMixin
from netbox.search import SearchIndex, register_search
from netbox.plugins.utils import get_plugin_config
from utilities.querysets import RestrictedQuerySet
from ipam.models import IPAddress
from ipam.choices import IPAddressFamilyChoices

from netbox_dns.choices import (
    RecordClassChoices,
    RecordTypeChoices,
    ZoneStatusChoices,
    ZoneEPPStatusChoices,
)
from netbox_dns.fields import NetworkField, RFC2317NetworkField
from netbox_dns.utilities import (
    update_dns_records,
    check_dns_records,
    get_ip_addresses_by_zone,
    arpa_to_prefix,
    name_to_unicode,
    normalize_name,
    get_parent_zone_names,
    regex_from_list,
    NameFormatError,
)
from netbox_dns.validators import (
    validate_rname,
    validate_domain_name,
)
from netbox_dns.mixins import ObjectModificationMixin

from .record import Record
from .view import View
from .nameserver import NameServer

__all__ = (
    "Zone",
    "ZoneIndex",
)

ZONE_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "zone_active_status")
RECORD_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "record_active_status")


class ZoneManager(models.Manager.from_queryset(RestrictedQuerySet)):
    """
    Custom manager for zones providing the activity status annotation
    """

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(
                active=ExpressionWrapper(
                    Q(status__in=ZONE_ACTIVE_STATUS_LIST), output_field=BooleanField()
                )
            )
        )


class Zone(ObjectModificationMixin, ContactsMixin, PrimaryModel):
    class Meta:
        verbose_name = _("Zone")
        verbose_name_plural = _("Zones")

        ordering = (
            "view",
            "name",
        )

        constraints = (
            UniqueConstraint(
                Lower("name"),
                "view",
                name="name_view_unique_ci",
                violation_error_message=_(
                    "There is already a zone with the same name in this view"
                ),
            ),
        )

        indexes = (
            models.Index(fields=["name"], name="netbox_dns_zone_name"),
            models.Index(
                fields=["rfc2317_prefix"], name="netbox_dns_zone_rfc2317_prefix"
            ),
            models.Index(fields=["arpa_network"], name="netbox_dns_zone_arpa_network"),
        )

    clone_fields = (
        "view",
        "name",
        "description",
        "status",
        "nameservers",
        "default_ttl",
        "soa_ttl",
        "soa_mname",
        "soa_rname",
        "soa_refresh",
        "soa_retry",
        "soa_expire",
        "soa_minimum",
        "tenant",
    )

    soa_clean_fields = {
        "description",
        "status",
        "dnssec_policy",
        "parental_agents",
        "registrar",
        "registry_domain_id",
        "expiration_date",
        "domain_status",
        "registrant",
        "admin_c",
        "tech_c",
        "billing_c",
        "rfc2317_parent_managed",
        "tenant",
        "comments",
        "owner",
    }

    objects = ZoneManager()

    def __str__(self):
        if self.name == "." and get_plugin_config("netbox_dns", "enable_root_zones"):
            name = ". (root zone)"
        else:
            try:
                name = dns_name.from_text(self.name, origin=None).to_unicode()
            except DNSException:
                name = self.name

        try:
            if not self.view.default_view:
                return f"[{self.view}] {name}"
        except ObjectDoesNotExist:
            return f"[<no view assigned>] {name}"

        return str(name)

    def __init__(self, *args, **kwargs):
        kwargs.pop("template", None)

        super().__init__(*args, **kwargs)

        self._soa_serial_dirty = False
        self._ip_addresses_checked = False

    view = models.ForeignKey(
        verbose_name=_("View"),
        to="View",
        on_delete=models.PROTECT,
        related_name="zones",
        null=False,
    )
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        db_collation="natural_sort",
    )
    status = models.CharField(
        verbose_name=_("Status"),
        max_length=50,
        choices=ZoneStatusChoices,
        default=ZoneStatusChoices.STATUS_ACTIVE,
        blank=True,
    )
    nameservers = models.ManyToManyField(
        verbose_name=_("Nameserver"),
        to="NameServer",
        related_name="zones",
        blank=True,
    )
    default_ttl = models.PositiveIntegerField(
        verbose_name=_("Default TTL"),
        blank=True,
        validators=[MaxValueValidator(2147483647)],
    )
    soa_ttl = models.PositiveIntegerField(
        verbose_name=_("SOA TTL"),
        blank=False,
        null=False,
        validators=[MaxValueValidator(2147483647)],
    )
    soa_mname = models.ForeignKey(
        verbose_name=_("SOA MName"),
        to="NameServer",
        related_name="soa_zones",
        on_delete=models.PROTECT,
        blank=False,
        null=False,
    )
    soa_rname = models.CharField(
        verbose_name=_("SOA RName"),
        max_length=255,
        blank=False,
        null=False,
    )
    soa_serial = models.BigIntegerField(
        verbose_name=_("SOA Serial"),
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(4294967295)],
    )
    soa_refresh = models.PositiveIntegerField(
        verbose_name=_("SOA Refresh"),
        blank=False,
        null=False,
        validators=[MinValueValidator(1)],
    )
    soa_retry = models.PositiveIntegerField(
        verbose_name=_("SOA Retry"),
        blank=False,
        null=False,
        validators=[MinValueValidator(1)],
    )
    soa_expire = models.PositiveIntegerField(
        verbose_name=_("SOA Expire"),
        blank=False,
        null=False,
        validators=[MinValueValidator(1)],
    )
    soa_minimum = models.PositiveIntegerField(
        verbose_name=_("SOA Minimum TTL"),
        blank=False,
        null=False,
        validators=[MaxValueValidator(2147483647)],
    )
    soa_serial_auto = models.BooleanField(
        verbose_name=_("Generate SOA Serial"),
        help_text=_("Automatically generate the SOA serial number"),
        default=True,
    )
    dnssec_policy = models.ForeignKey(
        verbose_name=_("DNSSEC Policy"),
        to="DNSSECPolicy",
        on_delete=models.PROTECT,
        related_name="zones",
        blank=True,
        null=True,
    )
    parental_agents = ArrayField(
        base_field=models.GenericIPAddressField(
            protocol="both",
        ),
        blank=True,
        null=True,
        default=list,
    )
    registrar = models.ForeignKey(
        verbose_name=_("Registrar"),
        to="Registrar",
        on_delete=models.SET_NULL,
        related_name="zones",
        blank=True,
        null=True,
    )
    registry_domain_id = models.CharField(
        verbose_name=_("Registry Domain ID"),
        max_length=50,
        blank=True,
        null=True,
    )
    expiration_date = models.DateField(
        verbose_name=_("Expiration Date"),
        blank=True,
        null=True,
    )
    domain_status = models.CharField(
        verbose_name=_("Domain Status"),
        max_length=50,
        choices=ZoneEPPStatusChoices,
        blank=True,
        null=True,
    )
    registrant = models.ForeignKey(
        verbose_name=_("Registrant"),
        to="RegistrationContact",
        on_delete=models.SET_NULL,
        related_name="registrant_zones",
        blank=True,
        null=True,
    )
    admin_c = models.ForeignKey(
        verbose_name=_("Administrative Contact"),
        to="RegistrationContact",
        on_delete=models.SET_NULL,
        related_name="admin_c_zones",
        blank=True,
        null=True,
    )
    tech_c = models.ForeignKey(
        verbose_name=_("Technical Contact"),
        to="RegistrationContact",
        on_delete=models.SET_NULL,
        related_name="tech_c_zones",
        blank=True,
        null=True,
    )
    billing_c = models.ForeignKey(
        verbose_name=_("Billing Contact"),
        to="RegistrationContact",
        on_delete=models.SET_NULL,
        related_name="billing_c_zones",
        blank=True,
        null=True,
    )
    rfc2317_prefix = RFC2317NetworkField(
        verbose_name=_("RFC2317 Prefix"),
        help_text=_("RFC2317 IPv4 prefix with a length of at least 25 bits"),
        blank=True,
        null=True,
    )
    rfc2317_parent_managed = models.BooleanField(
        verbose_name=_("RFC2317 Parent Managed"),
        help_text=_("The parent zone for the RFC2317 zone is managed by NetBox DNS"),
        default=False,
    )
    rfc2317_parent_zone = models.ForeignKey(
        verbose_name=_("RFC2317 Parent Zone"),
        to="self",
        on_delete=models.SET_NULL,
        related_name="rfc2317_child_zones",
        help_text=_("Parent zone for RFC2317 reverse zones"),
        blank=True,
        null=True,
    )
    arpa_network = NetworkField(
        verbose_name=_("ARPA Network"),
        help_text=_("Network related to a reverse lookup zone (.arpa)"),
        blank=True,
        null=True,
    )
    tenant = models.ForeignKey(
        verbose_name=_("Tenant"),
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="netbox_dns_zones",
        blank=True,
        null=True,
    )

    @property
    def fqdn(self):
        return f"{self.name}."

    @staticmethod
    def get_defaults():
        default_fields = (
            "zone_default_ttl",
            "zone_soa_ttl",
            "zone_soa_serial",
            "zone_soa_refresh",
            "zone_soa_retry",
            "zone_soa_expire",
            "zone_soa_minimum",
            "zone_soa_rname",
        )

        return {
            field[5:]: value
            for field, value in settings.PLUGINS_CONFIG.get("netbox_dns").items()
            if field in default_fields
        }

    @property
    def soa_serial_dirty(self):
        return self._soa_serial_dirty

    @soa_serial_dirty.setter
    def soa_serial_dirty(self, soa_serial_dirty):
        self._soa_serial_dirty = soa_serial_dirty

    @property
    def ip_addresses_checked(self):
        return self._ip_addresses_checked

    @ip_addresses_checked.setter
    def ip_addresses_checked(self, ip_addresses_checked):
        self._ip_addresses_checked = ip_addresses_checked

    @property
    def display_name(self):
        return name_to_unicode(self.name)

    def get_status_color(self):
        return ZoneStatusChoices.colors.get(self.status)

    def get_domain_status_color(self):
        return ZoneEPPStatusChoices.colors.get(self.domain_status)

    def get_status_class(self):
        return self.CSS_CLASSES.get(self.status)

    @property
    def is_active(self):
        return self.status in ZONE_ACTIVE_STATUS_LIST

    @property
    def is_reverse_zone(self):
        return self.name.endswith(".arpa") and self.network_from_name is not None

    @property
    def is_rfc2317_zone(self):
        return self.rfc2317_prefix is not None

    @property
    def inline_signing(self):
        if self.dnssec_policy is None:
            return None

        return self.dnssec_policy.inline_signing

    def get_rfc2317_parent_zone(self):
        if not self.is_rfc2317_zone:
            return None

        return (
            self.view.zones.filter(arpa_network__net_contains=self.rfc2317_prefix)
            .order_by("arpa_network__net_mask_length")
            .last()
        )

    @property
    def is_registered(self):
        return any(
            field is not None
            for field in (
                self.registrar,
                self.registry_domain_id,
                self.registrant,
                self.admin_c,
                self.tech_c,
                self.billing_c,
                self.expiration_date,
                self.domain_status,
            )
        )

    @property
    def child_zones(self):
        return self.view.zones.filter(name__iregex=rf"^[^.]+\.{re.escape(self.name)}$")

    @property
    def descendant_zones(self):
        return self.view.zones.filter(name__iendswith=f".{self.name}")

    @property
    def parent_zone(self):
        try:
            return self.view.zones.get(
                name__iexact=get_parent_zone_names(self.name)[-1]
            )
        except (Zone.DoesNotExist, IndexError):
            return None

    @property
    def ancestor_zones(self):
        return (
            self.view.zones.annotate(name_length=Length("name"))
            .filter(name__iregex=regex_from_list(get_parent_zone_names(self.name)))
            .order_by("name_length")
        )

    @property
    def delegation_records(self):
        descendant_zone_names = [
            rf"{name}."
            for name in (
                name.lower()
                for name in self.descendant_zones.values_list("name", flat=True)
            )
        ]

        ns_records = (
            self.records.filter(type=RecordTypeChoices.NS)
            .exclude(fqdn__iexact=self.fqdn)
            .filter(fqdn__iregex=regex_from_list(descendant_zone_names))
        )
        ns_values = [record.value_fqdn for record in ns_records]

        return (
            ns_records
            | self.records.filter(type=RecordTypeChoices.DS)
            | self.records.filter(
                type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA),
                fqdn__in=ns_values,
            )
        )

    @property
    def ancestor_delegation_records(self):
        ancestor_zones = self.ancestor_zones

        ns_records = Record.objects.filter(
            type=RecordTypeChoices.NS, zone__in=ancestor_zones, fqdn=self.fqdn
        )
        ns_values = [record.value_fqdn for record in ns_records]

        ds_records = Record.objects.filter(
            type=RecordTypeChoices.DS, zone__in=ancestor_zones, fqdn=self.fqdn
        )

        return (
            ns_records
            | ds_records
            | Record.objects.filter(
                zone__in=ancestor_zones,
                type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA),
                fqdn__in=ns_values,
            )
        )

    def update_soa_record(self):
        soa_name = "@"
        soa_ttl = self.soa_ttl
        soa_rdata = SOA.SOA(
            rdclass=RecordClassChoices.IN,
            rdtype=RecordTypeChoices.SOA,
            mname=self.soa_mname.name,
            rname=self.soa_rname,
            serial=self.soa_serial,
            refresh=self.soa_refresh,
            retry=self.soa_retry,
            expire=self.soa_expire,
            minimum=self.soa_minimum,
        )

        try:
            soa_record = self.records.get(type=RecordTypeChoices.SOA, name=soa_name)

            if (
                soa_record.ttl != soa_ttl
                or soa_record.value != soa_rdata.to_text()
                or not soa_record.managed
            ):
                soa_record.snapshot()
                soa_record.ttl = soa_ttl
                soa_record.value = soa_rdata.to_text()
                soa_record.managed = True
                soa_record.save()

        except Record.DoesNotExist:
            Record.objects.create(
                zone_id=self.pk,
                type=RecordTypeChoices.SOA,
                name=soa_name,
                ttl=soa_ttl,
                value=soa_rdata.to_text(),
                managed=True,
            )

    update_soa_record.alters_data = True

    def update_ns_records(self):
        ns_name = "@"

        nameservers = [f"{nameserver.name}." for nameserver in self.nameservers.all()]

        for ns_record in self.records.filter(
            type=RecordTypeChoices.NS, managed=True
        ).exclude(value__in=nameservers):
            ns_record.delete()

        for ns in nameservers:
            Record.raw_objects.update_or_create(
                zone_id=self.pk,
                type=RecordTypeChoices.NS,
                name=ns_name,
                value=ns,
                managed=True,
            )

    update_ns_records.alters_data = True

    def _check_nameserver_address_records(self, nameserver):
        name = dns_name.from_text(nameserver.name, origin=None)
        parent = name.parent()

        if len(parent) < 2:
            return None

        try:
            ns_zone = Zone.objects.get(view_id=self.view.pk, name=parent.to_text())
        except ObjectDoesNotExist:
            return None

        relative_name = name.relativize(parent).to_text()
        address_records = ns_zone.records.filter(
            Q(status__in=RECORD_ACTIVE_STATUS_LIST),
            Q(Q(name=f"{nameserver.name}.") | Q(name=relative_name)),
            Q(Q(type=RecordTypeChoices.A) | Q(type=RecordTypeChoices.AAAA)),
        )

        if not address_records.exists():
            return _(
                "Nameserver {ns} does not have an active address record in zone {zone}"
            ).format(ns=nameserver.name, zone=ns_zone)

    def check_nameservers(self):
        nameservers = self.nameservers.all()

        ns_warnings = []
        ns_errors = []

        if not nameservers:
            ns_errors.append(
                _("No nameservers are configured for zone {zone}").format(zone=self)
            )

        for _nameserver in nameservers:
            warning = self._check_nameserver_address_records(_nameserver)
            if warning is not None:
                ns_warnings.append(warning)

        return ns_warnings, ns_errors

    def check_expiration(self):
        if self.expiration_date is None:
            return None, None

        expiration_warning = None
        expiration_error = None

        expiration_warning_days = get_plugin_config(
            "netbox_dns", "zone_expiration_warning_days"
        )

        if self.expiration_date < date.today():
            expiration_error = _("The registration for this domain has expired.")
        elif (self.expiration_date - date.today()).days < expiration_warning_days:
            expiration_warning = _(
                f"The registration for this domain will expire in less than {expiration_warning_days} days."
            )

        return expiration_warning, expiration_error

    def check_soa_serial_increment(self, old_serial, new_serial):
        MAX_SOA_SERIAL_INCREMENT = 2**31 - 1
        SOA_SERIAL_WRAP = 2**32

        if old_serial is None:
            return

        if (new_serial - old_serial) % SOA_SERIAL_WRAP > MAX_SOA_SERIAL_INCREMENT:
            raise ValidationError(
                {
                    "soa_serial": _(
                        "soa_serial must not decrease for zone {zone}."
                    ).format(zone=self.name)
                }
            )

    def get_auto_serial(self):
        records = Record.objects.filter(zone_id=self.pk).exclude(
            type=RecordTypeChoices.SOA
        )
        if records:
            soa_serial = (
                records.aggregate(Max("last_updated"))
                .get("last_updated__max")
                .timestamp()
            )
        else:
            soa_serial = ceil(datetime.now().timestamp())

        if self.last_updated:
            soa_serial = ceil(max(soa_serial, self.last_updated.timestamp()))

        return soa_serial

    def update_serial(self, save_zone_serial=True):
        if not self.soa_serial_auto:
            return

        self.last_updated = datetime.now()
        self.soa_serial = ceil(datetime.now().timestamp())

        if save_zone_serial:
            super().save(update_fields=["soa_serial", "last_updated"])
            self.soa_serial_dirty = False
            self.update_soa_record()
        else:
            self.soa_serial_dirty = True

    update_serial.alters_data = True

    def save_soa_serial(self):
        if self.soa_serial_auto and self.soa_serial_dirty:
            super().save(update_fields=["soa_serial", "last_updated"])
            self.soa_serial_dirty = False

    save_soa_serial.alters_data = True

    @property
    def network_from_name(self):
        return arpa_to_prefix(self.name)

    def update_rfc2317_parent_zone(self):
        if not self.is_rfc2317_zone:
            return

        if self.rfc2317_parent_managed:
            rfc2317_parent_zone = self.get_rfc2317_parent_zone()

            if rfc2317_parent_zone is None:
                self.rfc2317_parent_managed = False
                self.rfc2317_parent_zone = None
                self.save(
                    update_fields=["rfc2317_parent_zone", "rfc2317_parent_managed"]
                )

            elif self.rfc2317_parent_zone != rfc2317_parent_zone:
                self.rfc2317_parent_zone = rfc2317_parent_zone
                self.save(update_fields=["rfc2317_parent_zone"])

        ptr_records = self.records.filter(type=RecordTypeChoices.PTR).prefetch_related(
            "zone", "rfc2317_cname_record"
        )
        ptr_zones = {ptr_record.zone for ptr_record in ptr_records}

        if self.rfc2317_parent_managed:
            for ptr_record in ptr_records:
                ptr_record.save(save_zone_serial=False)

            self.rfc2317_parent_zone.save_soa_serial()
            self.rfc2317_parent_zone.update_soa_record()
        else:
            cname_records = {
                ptr_record.rfc2317_cname_record
                for ptr_record in ptr_records
                if ptr_record.rfc2317_cname_record is not None
            }
            cname_zones = {cname_record.zone for cname_record in cname_records}

            for ptr_record in ptr_records:
                ptr_record.save(update_rfc2317_cname=False, save_zone_serial=False)
            for cname_record in cname_records:
                cname_record.delete(save_zone_serial=False)

            for cname_zone in cname_zones:
                cname_zone.save_soa_serial()
                cname_zone.update_soa_record()

        for ptr_zone in ptr_zones:
            ptr_zone.save_soa_serial()
            ptr_zone.update_soa_record()

    def clean_fields(self, exclude=None):
        defaults = settings.PLUGINS_CONFIG.get("netbox_dns")

        if get_plugin_config("netbox_dns", "convert_names_to_lowercase", False):
            self.name = self.name.lower()

        if self.view_id is None:
            self.view_id = View.get_default_view().pk

        for field, value in self.get_defaults().items():
            if getattr(self, field) in (None, ""):
                if value not in (None, ""):
                    setattr(self, field, value)

        if self.soa_mname_id is None and "soa_mname" not in exclude:
            if default_soa_mname := defaults.get("zone_soa_mname"):
                try:
                    self.soa_mname = NameServer.objects.get(name=default_soa_mname)
                except NameServer.DoesNotExist:
                    raise ValidationError(
                        {
                            "soa_mname": _(
                                "Default soa_mname instance {nameserver} does not exist"
                            ).format(nameserver=default_soa_mname)
                        }
                    )
            else:
                raise ValidationError(
                    {
                        "soa_mname": _(
                            "soa_mname not set and no template or default value defined"
                        )
                    }
                )

        super().clean_fields(exclude=exclude)

    clean_fields.alters_data = True

    def clean(self, *args, **kwargs):
        if not self.dnssec_policy:
            self.parental_agents = self._meta.get_field("parental_agents").get_default()

        if not self.registrar:
            self.registry_domain_id = self._meta.get_field(
                "registry_domain_id"
            ).get_default()
            self.expiration_date = self._meta.get_field("expiration_date").get_default()
            self.domain_status = self._meta.get_field("domain_status").get_default()

        if self.soa_ttl is None:
            self.soa_ttl = self.default_ttl

        try:
            self.name = normalize_name(self.name)
        except NameFormatError as exc:
            raise ValidationError(
                {
                    "name": str(exc),
                }
            )

        try:
            validate_domain_name(self.name, zone_name=True)
        except ValidationError as exc:
            raise ValidationError(
                {
                    "name": exc,
                }
            )

        if self.soa_rname in (None, ""):
            raise ValidationError(
                {
                    "soa_rname": _(
                        "soa_rname not set and no template or default value defined"
                    ),
                }
            )
        try:
            dns_name.from_text(self.soa_rname, origin=dns_name.root)
            validate_rname(self.soa_rname)
        except (DNSException, ValidationError) as exc:
            raise ValidationError(
                {
                    "soa_rname": exc,
                }
            )

        if not self.soa_serial_auto:
            if self.soa_serial is None:
                raise ValidationError(
                    {
                        "soa_serial": _(
                            "soa_serial is not defined and soa_serial_auto is disabled for zone {zone}."
                        ).format(zone=self.name)
                    }
                )

        if not self._state.adding:
            old_soa_serial = self.get_saved_value("soa_serial")
            old_soa_serial_auto = self.get_saved_value("soa_serial_auto")

            if not self.soa_serial_auto:
                self.check_soa_serial_increment(old_soa_serial, self.soa_serial)
            elif not old_soa_serial_auto:
                try:
                    self.check_soa_serial_increment(
                        old_soa_serial, self.get_auto_serial()
                    )
                except ValidationError:
                    raise ValidationError(
                        {
                            "soa_serial_auto": _(
                                "Enabling soa_serial_auto would decrease soa_serial for zone {zone}."
                            ).format(zone=self.name)
                        }
                    )

            old_name = self.get_saved_value("name")
            old_view_id = self.get_saved_value("view_id")

            if (
                not self.ip_addresses_checked
                and old_name != self.name
                or old_view_id != self.view_id
            ):
                ip_addresses = IPAddress.objects.filter(
                    netbox_dns_records__in=self.records.filter(
                        ipam_ip_address__isnull=False
                    )
                )
                ip_addresses |= get_ip_addresses_by_zone(self)

                for ip_address in ip_addresses.distinct():
                    try:
                        check_dns_records(ip_address, zone=self)
                    except ValidationError as exc:
                        raise ValidationError(exc.messages)

                self.ip_addresses_checked = True

        if self.is_reverse_zone:
            self.arpa_network = self.network_from_name
        else:
            self.arpa_network = None

        if self.is_rfc2317_zone:
            if self.arpa_network is not None:
                raise ValidationError(
                    {
                        "rfc2317_prefix": _(
                            "A regular reverse zone can not be used as an RFC2317 zone."
                        )
                    }
                )

            if self.rfc2317_parent_managed:
                rfc2317_parent_zone = self.get_rfc2317_parent_zone()

                if rfc2317_parent_zone is None:
                    raise ValidationError(
                        {
                            "rfc2317_parent_managed": _(
                                "Parent zone not found in view {view}."
                            ).format(view=self.view)
                        }
                    )

                self.rfc2317_parent_zone = rfc2317_parent_zone
            else:
                self.rfc2317_parent_zone = None

            overlapping_zones = self.view.zones.filter(
                rfc2317_prefix__net_overlap=self.rfc2317_prefix,
                active=True,
            ).exclude(pk=self.pk)

            if overlapping_zones.exists():
                raise ValidationError(
                    {
                        "rfc2317_prefix": _(
                            "RFC2317 prefix overlaps with zone {zone}."
                        ).format(zone=overlapping_zones.first())
                    }
                )

        else:
            self.rfc2317_parent_managed = False
            self.rfc2317_parent_zone = None

        super().clean(*args, **kwargs)

    clean.alters_data = True

    def save(self, *args, **kwargs):
        self.full_clean()

        changed_fields = self.changed_fields

        if self.soa_serial_auto and (
            changed_fields is None or changed_fields - self.soa_clean_fields
        ):
            self.soa_serial = self.get_auto_serial()

        super().save(*args, **kwargs)

        if (
            changed_fields is None or {"name", "view", "status"} & changed_fields
        ) and self.is_reverse_zone:
            zones = self.view.zones.filter(
                arpa_network__net_contains_or_equals=self.arpa_network
            )

            if self.arpa_network.version == IPAddressFamilyChoices.FAMILY_4:
                record_type = RecordTypeChoices.A
            else:
                record_type = RecordTypeChoices.AAAA

            address_records = Record.objects.filter(
                Q(
                    ptr_record__isnull=True,
                    zone__view=self.view,
                    ip_address__isnull=False,
                    ip_address__contained=self.arpa_network,
                    type=record_type,
                )
                | Q(ptr_record__zone__in=zones),
                disable_ptr=False,
            )

            for address_record in address_records:
                address_record.save(
                    update_fields=["ptr_record"], save_zone_serial=False
                )

            for zone in zones:
                zone.save_soa_serial()

            if self.arpa_network.version == 4:
                rfc2317_child_zones = Zone.objects.filter(
                    rfc2317_prefix__net_contained=self.arpa_network,
                    rfc2317_parent_managed=True,
                )
                for child_zone in rfc2317_child_zones:
                    child_zone.update_rfc2317_parent_zone()

        if (
            changed_fields is None
            or {"name", "view", "status", "rfc2317_prefix", "rfc2317_parent_managed"}
            & changed_fields
        ) and self.is_rfc2317_zone:
            zones = self.view.zones.filter(
                arpa_network__net_contains=self.rfc2317_prefix
            )
            address_records = Record.objects.filter(
                Q(ptr_record__isnull=True, ip_address__contained=self.rfc2317_prefix)
                | Q(ptr_record__zone__in=zones)
                | Q(ptr_record__zone=self),
                type=RecordTypeChoices.A,
                disable_ptr=False,
            )

            for address_record in address_records:
                address_record.save(
                    update_fields=["ptr_record"],
                    update_rfc2317_cname=False,
                    save_zone_serial=False,
                )

            for zone in zones:
                zone.save_soa_serial()

            self.update_rfc2317_parent_zone()

        elif changed_fields is not None and {"name", "view", "status"} & changed_fields:
            for address_record in self.records.filter(
                type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA),
                ipam_ip_address__isnull=True,
            ):
                address_record.save(update_fields=["ptr_record"])

        if changed_fields is not None and "name" in changed_fields:
            for _record in self.records.filter(ipam_ip_address__isnull=True):
                _record.save(
                    update_fields=["fqdn"],
                    save_zone_serial=False,
                    update_rrset_ttl=False,
                    update_rfc2317_cname=False,
                )

        if changed_fields is None or {"name", "view"} & changed_fields:
            ip_addresses = IPAddress.objects.filter(
                netbox_dns_records__in=self.records.filter(
                    ipam_ip_address__isnull=False
                )
            )
            ip_addresses |= get_ip_addresses_by_zone(self)

            for ip_address in ip_addresses.distinct():
                update_dns_records(ip_address)

        if (
            self.rfc2317_prefix is not None
            and changed_fields is not None
            and "rfc2317_prefix" in changed_fields
        ):
            for zone in self.rfc2317_child_zones.all():
                zone.update_rfc2317_parent_zone()

        self.save_soa_serial()
        self.update_soa_record()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            address_records = self.records.filter(
                ptr_record__isnull=False
            ).prefetch_related("ptr_record")
            for address_record in address_records:
                address_record.ptr_record.delete()

            ptr_records = self.records.filter(address_records__isnull=False)
            update_records = list(
                Record.objects.filter(ptr_record__in=ptr_records).values_list(
                    "pk", flat=True
                )
            )

            cname_records = {
                ptr_record.rfc2317_cname_record
                for ptr_record in ptr_records
                if ptr_record.rfc2317_cname_record is not None
            }
            cname_zones = {cname_record.zone for cname_record in cname_records}

            for cname_record in cname_records:
                cname_record.delete(save_zone_serial=False)
            for cname_zone in cname_zones:
                cname_zone.save_soa_serial()
                cname_zone.update_soa_record()

            rfc2317_child_zones = list(
                self.rfc2317_child_zones.values_list("pk", flat=True)
            )

            ipam_ip_addresses = list(
                IPAddress.objects.filter(
                    netbox_dns_records__in=self.records.filter(
                        ipam_ip_address__isnull=False
                    )
                )
                .distinct()
                .values_list("pk", flat=True)
            )

            super().delete(*args, **kwargs)

        address_records = Record.objects.filter(pk__in=update_records).prefetch_related(
            "zone"
        )

        for address_record in address_records:
            address_record.save(save_zone_serial=False)
        for address_zone in {address_record.zone for address_record in address_records}:
            address_zone.save_soa_serial()
            address_zone.update_soa_record()

        ip_addresses = IPAddress.objects.filter(pk__in=ipam_ip_addresses)
        for ip_address in ip_addresses:
            update_dns_records(ip_address)

        rfc2317_child_zones = Zone.objects.filter(pk__in=rfc2317_child_zones)
        if rfc2317_child_zones:
            for child_zone in rfc2317_child_zones:
                child_zone.update_rfc2317_parent_zone()

            new_rfc2317_parent_zone = rfc2317_child_zones.first().rfc2317_parent_zone
            if new_rfc2317_parent_zone is not None:
                new_rfc2317_parent_zone.save_soa_serial()
                new_rfc2317_parent_zone.update_soa_record()


@receiver(m2m_changed, sender=Zone.nameservers.through)
def update_ns_records(**kwargs):
    if kwargs.get("action") not in ["post_add", "post_remove"]:
        return

    zone = kwargs.get("instance")
    zone.update_ns_records()


@register_search
class ZoneIndex(SearchIndex):
    model = Zone

    fields = (
        ("name", 100),
        ("view", 150),
        ("registrar", 300),
        ("registry_domain_id", 300),
        ("registrant", 300),
        ("admin_c", 300),
        ("tech_c", 300),
        ("billing_c", 300),
        ("description", 500),
        ("soa_rname", 1000),
        ("soa_mname", 1000),
        ("arpa_network", 1000),
    )
