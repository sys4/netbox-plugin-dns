from django import forms
from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.contrib.postgres.forms import SimpleArrayField
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from netbox.context import events_queue
from utilities.forms.fields import (
    DynamicModelMultipleChoiceField,
    TagFilterField,
    CSVChoiceField,
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelChoiceField,
)
from utilities.forms.widgets import BulkEditNullBooleanSelect, DatePicker, HTMXSelect
from utilities.forms.rendering import FieldSet
from utilities.forms import (
    BOOLEAN_WITH_BLANK_CHOICES,
    add_blank_choice,
    get_field_value,
)
from tenancy.models import Tenant, TenantGroup
from tenancy.forms import TenancyForm, TenancyFilterForm

from netbox_dns.models import (
    View,
    Zone,
    NameServer,
    Registrar,
    RegistrationContact,
    ZoneTemplate,
    DNSSECPolicy,
)
from netbox_dns.choices import ZoneStatusChoices, ZoneEPPStatusChoices
from netbox_dns.utilities import name_to_unicode, network_to_reverse
from netbox_dns.fields import RFC2317NetworkFormField, TimePeriodField
from netbox_dns.validators import validate_ipv4, validate_prefix, validate_rfc2317

__all__ = (
    "ZoneForm",
    "ZoneFilterForm",
    "ZoneImportForm",
    "ZoneBulkEditForm",
)


class RollbackTransaction(Exception):
    pass


class ZoneTemplateUpdateMixin:
    def _check_soa_mname(self):
        if (
            self.cleaned_data.get("soa_mname") is None
            and "soa_mname" in self.fields.keys()
        ):
            self.add_error(
                "soa_mname",
                _("soa_mname not set and no template or default value defined"),
            )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        if (template := self.cleaned_data.get("template")) is None:
            self._check_soa_mname()
            return

        if not self.cleaned_data.get("nameservers") and template.nameservers.all():
            self.cleaned_data["nameservers"] = template.nameservers.all()

        if not self.cleaned_data.get("tags") and template.tags.all():
            self.cleaned_data["tags"] = template.tags.all()

        for field in template.template_fields:
            if self.cleaned_data.get(field) in (None, "", []) and getattr(
                template, field
            ) not in (None, "", []):
                self.cleaned_data[field] = getattr(template, field)

        self._check_soa_mname()

        if self.errors:
            return

        saved_events_queue = events_queue.get()

        try:
            with transaction.atomic():
                if self.instance.id is not None:
                    if hasattr(self, "_post_clean"):
                        super()._post_clean()
                    zone = super().save(*args, **kwargs)
                else:
                    zone_data = self.cleaned_data.copy()

                    custom_fields = {}
                    for key, value in zone_data.copy().items():
                        if key.startswith("cf_"):
                            if isinstance(value, models.Model):
                                custom_fields[key[3:]] = value.pk
                            elif isinstance(value, models.QuerySet):
                                custom_fields[key[3:]] = list(
                                    value.values_list("pk", flat=True)
                                )
                            else:
                                custom_fields[key[3:]] = value
                            zone_data.pop(key)
                    if custom_fields:
                        zone_data["custom_field_data"] = custom_fields

                    zone_data.pop("template", None)
                    zone_data.pop("tenant_group", None)
                    zone_data.pop("owner_group", None)
                    zone_data.pop("_init_time", None)

                    nameservers = zone_data.pop("nameservers")
                    tags = zone_data.pop("tags")

                    zone = Zone.objects.create(**zone_data)

                    zone.nameservers.set(nameservers)
                    zone.tags.set(tags)

                template.create_records(zone)
                raise RollbackTransaction

        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field_name in self.fields.keys():
                    exc.error_dict.pop(field_name, None)
                errors = exc.error_dict.values()
            else:
                errors = exc.messages

            for error in errors:
                self.add_error("template", error)

        except RollbackTransaction:
            pass

        events_queue.set(saved_events_queue)

        return self.cleaned_data

    def save(self, *args, **kwargs):
        zone = super().save(*args, **kwargs)

        if (template := self.cleaned_data.get("template")) is not None:
            template.create_records(zone)

        return zone


class ZoneForm(ZoneTemplateUpdateMixin, TenancyForm, PrimaryModelForm):
    class Meta:
        model = Zone

        fields = (
            "name",
            "description",
            "owner",
            "comments",
            "view",
            "status",
            "template",
            "nameservers",
            "default_ttl",
            "soa_ttl",
            "soa_mname",
            "soa_rname",
            "soa_serial_auto",
            "soa_serial",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
            "rfc2317_prefix",
            "rfc2317_parent_managed",
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
            "tenant_group",
            "tenant",
            "comments",
            "tags",
        )

        labels = {
            "soa_serial_auto": _("Generate SOA Serial"),
            "rfc2317_parent_managed": _("RFC2317 Parent Managed"),
        }

        help_texts = {
            "soa_serial_auto": _("Automatically generate the SOA serial number"),
            "rfc2317_parent_managed": _(
                "IPv4 reverse zone for delegating the RFC2317 PTR records is managed in NetBox DNS"
            ),
        }

        widgets = {
            "dnssec_policy": HTMXSelect(),
            "registrar": HTMXSelect(),
            "expiration_date": DatePicker,
        }

    fieldsets = (
        FieldSet(
            "view",
            "name",
            "description",
            "template",
            "status",
            "nameservers",
            "default_ttl",
            name=_("Zone"),
        ),
        FieldSet(
            "soa_ttl",
            "soa_mname",
            "soa_rname",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
            "soa_serial_auto",
            "soa_serial",
            name=_("SOA"),
        ),
        FieldSet(
            "dnssec_policy",
            "parental_agents",
            name=_("DNSSEC"),
        ),
        FieldSet(
            "rfc2317_prefix",
            "rfc2317_parent_managed",
            name=_("RFC2317"),
        ),
        FieldSet(
            "registrar",
            "registry_domain_id",
            "expiration_date",
            "domain_status",
            "registrant",
            "admin_c",
            "tech_c",
            "billing_c",
            name=_("Domain Registration"),
        ),
        FieldSet(
            "tenant_group",
            "tenant",
            name=_("Tenancy"),
        ),
        FieldSet(
            "tags",
            name=_("Tags"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        initial_name = self.initial.get("name")
        if initial_name:
            self.initial["name"] = name_to_unicode(initial_name)

        if self.initial.get("view") is None:
            self.initial["view"] = View.get_default_view()

        defaults = settings.PLUGINS_CONFIG.get("netbox_dns")
        for setting in (
            "default_ttl",
            "soa_ttl",
            "soa_rname",
            "soa_serial_auto",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
        ):
            if self.initial.get(setting) in (None, ""):
                self.initial[setting] = defaults.get(f"zone_{setting}")

        if self.initial.get("soa_ttl") is None:
            self.initial["soa_ttl"] = self.initial.get("default_ttl")

        if self.initial.get("soa_mname") is None:
            default_soa_mname = defaults.get("zone_soa_mname")
            if default_soa_mname is not None:
                try:
                    self.initial["soa_mname"] = NameServer.objects.get(
                        name=default_soa_mname
                    )
                except NameServer.DoesNotExist:
                    pass

        if not self.initial.get("nameservers", []):
            default_nameservers = defaults.get("zone_nameservers", [])
            if default_nameservers:
                self.initial["nameservers"] = NameServer.objects.filter(
                    name__in=default_nameservers
                )

        if not get_field_value(self, "dnssec_policy"):
            del self.fields["parental_agents"]

        if not get_field_value(self, "registrar"):
            del self.fields["registry_domain_id"]
            del self.fields["expiration_date"]
            del self.fields["domain_status"]

    view = DynamicModelChoiceField(
        queryset=View.objects.all(),
        required=True,
        label=_("View"),
    )
    template = DynamicModelChoiceField(
        queryset=ZoneTemplate.objects.all(),
        required=False,
        label=_("Template"),
    )
    nameservers = DynamicModelMultipleChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        label=_("Nameservers"),
    )
    default_ttl = TimePeriodField(
        required=False,
        help_text=_("Default TTL for new records in this zone"),
        validators=[MinValueValidator(1)],
        label=_("Default TTL"),
    )
    soa_ttl = TimePeriodField(
        required=True,
        help_text=_("TTL for the SOA record of the zone"),
        validators=[MinValueValidator(1)],
        label=_("SOA TTL"),
    )
    soa_mname = DynamicModelChoiceField(
        queryset=NameServer.objects.all(),
        help_text=_("Primary nameserver this zone"),
        required=False,
        label=_("SOA MName"),
    )
    soa_rname = forms.CharField(
        required=False,
        help_text=_("Mailbox of the zone's administrator"),
        label=_("SOA RName"),
    )
    soa_refresh = TimePeriodField(
        required=True,
        help_text=_("Refresh interval for secondary nameservers"),
        validators=[MinValueValidator(1)],
        label=_("SOA Refresh"),
    )
    soa_retry = TimePeriodField(
        required=True,
        help_text=_("Retry interval for secondary nameservers"),
        validators=[MinValueValidator(1)],
        label=_("SOA Retry"),
    )
    soa_expire = TimePeriodField(
        required=True,
        validators=[MinValueValidator(1)],
        help_text=_("Expire time after which the zone is considered unavailable"),
        label=_("SOA Expire"),
    )
    soa_minimum = TimePeriodField(
        required=True,
        help_text=_("Minimum TTL for negative results, e.g. NXRRSET, NXDOMAIN"),
        validators=[MinValueValidator(1)],
        label=_("SOA Minimum TTL"),
    )
    soa_serial = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA Serial"),
    )
    parental_agents = SimpleArrayField(
        required=False,
        base_field=forms.GenericIPAddressField(),
        label=_("Parental Agents"),
    )
    rfc2317_prefix = RFC2317NetworkFormField(
        required=False,
        validators=[validate_ipv4, validate_prefix, validate_rfc2317],
        help_text=_("RFC2317 IPv4 prefix with a length of at least 25 bits"),
        label=_("RFC2317 Prefix"),
    )

    def clean_default_ttl(self):
        return (
            self.cleaned_data["default_ttl"]
            if self.cleaned_data["default_ttl"]
            else self.initial["default_ttl"]
        )

    def clean_name(self):
        name = self.cleaned_data["name"]
        if reverse_name := network_to_reverse(name):
            return reverse_name
        else:
            return name


class ZoneFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = Zone

    fieldsets = (
        FieldSet(
            "q",
            "filter_id",
            "tag",
        ),
        FieldSet(
            "owner_group_id",
            "owner_id",
            name=_("Ownership"),
        ),
        FieldSet(
            "name",
            "description",
            "view_id",
            "status",
            "nameserver_id",
            "active",
            "default_ttl",
            name=_("Attributes"),
        ),
        FieldSet(
            "soa_ttl",
            "soa_mname_id",
            "soa_rname",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
            "soa_serial",
            "soa_serial_auto",
            name=_("SOA"),
        ),
        FieldSet(
            "dnssec_policy_id",
            "inline_signing",
            "parental_agents",
            name=_("DNSSEC"),
        ),
        FieldSet(
            "rfc2317_prefix",
            "rfc2317_parent_managed",
            "rfc2317_parent_zone_id",
            name=_("RFC2317"),
        ),
        FieldSet(
            "registrar_id",
            "registry_domain_id",
            "expiration_date_before",
            "expiration_date_after",
            "domain_status",
            "registrant_id",
            "admin_c_id",
            "tech_c_id",
            "billing_c_id",
            name=_("Registration"),
        ),
        FieldSet(
            "tenant_group_id",
            "tenant_id",
            name=_("Tenancy"),
        ),
    )

    name = forms.CharField(
        required=False,
        label=_("Name"),
    )
    description = forms.CharField(
        required=False,
        label=_("Description"),
    )
    view_id = DynamicModelMultipleChoiceField(
        queryset=View.objects.all(),
        required=False,
        label=_("View"),
    )
    status = forms.MultipleChoiceField(
        choices=ZoneStatusChoices,
        required=False,
        label=_("Status"),
    )
    nameserver_id = DynamicModelMultipleChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Nameservers"),
    )
    active = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Active"),
    )
    default_ttl = TimePeriodField(
        required=False,
        label=_("Default TTL"),
    )
    soa_mname_id = DynamicModelMultipleChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        label=_("SOA MName"),
    )
    soa_rname = forms.CharField(
        required=False,
        label=_("SOA RName"),
    )
    soa_ttl = TimePeriodField(
        required=False,
        label=_("SOA TTL"),
    )
    soa_refresh = TimePeriodField(
        required=False,
        label=_("SOA Refresh"),
    )
    soa_retry = TimePeriodField(
        required=False,
        label=_("SOA Retry"),
    )
    soa_expire = TimePeriodField(
        required=False,
        label=_("SOA Expire"),
    )
    soa_minimum = TimePeriodField(
        required=False,
        label=_("SOA Minimum TTL"),
    )
    soa_serial = forms.IntegerField(
        required=False,
        label=_("SOA Serial"),
    )
    soa_serial_auto = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Generate SOA Serial"),
    )
    rfc2317_prefix = RFC2317NetworkFormField(
        required=False,
        label=_("Prefix"),
    )
    rfc2317_parent_managed = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Parent Managed"),
    )
    rfc2317_parent_zone_id = DynamicModelMultipleChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Parent Zone"),
    )
    dnssec_policy_id = DynamicModelMultipleChoiceField(
        queryset=DNSSECPolicy.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("DNSSEC Policy"),
    )
    inline_signing = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("DNSSEC Policy uses inline signing"),
    )
    parental_agents = forms.GenericIPAddressField(
        required=False,
        label=_("Parental Agents"),
    )
    registrar_id = DynamicModelMultipleChoiceField(
        queryset=Registrar.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Registrar"),
    )
    registry_domain_id = forms.CharField(
        required=False,
        label=_("Registry Domain ID"),
    )
    expiration_date_after = forms.DateField(
        required=False,
        label=_("Expiration Date after"),
        widget=DatePicker,
    )
    expiration_date_before = forms.DateField(
        required=False,
        label=_("Expiration Date before"),
        widget=DatePicker,
    )
    domain_status = forms.MultipleChoiceField(
        choices=ZoneEPPStatusChoices,
        required=False,
        label=_("Domain Status"),
    )
    registrant_id = DynamicModelMultipleChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Registrant"),
    )
    admin_c_id = DynamicModelMultipleChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Administrative Contact"),
    )
    tech_c_id = DynamicModelMultipleChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Technical Contact"),
    )
    billing_c_id = DynamicModelMultipleChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        null_option=_("None"),
        label=_("Billing Contact"),
    )
    tag = TagFilterField(Zone)


class ZoneImportForm(ZoneTemplateUpdateMixin, PrimaryModelImportForm):
    class Meta:
        model = Zone

        fields = (
            "view",
            "name",
            "description",
            "owner",
            "comments",
            "status",
            "template",
            "nameservers",
            "default_ttl",
            "soa_ttl",
            "soa_mname",
            "soa_rname",
            "soa_serial_auto",
            "soa_serial",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
            "dnssec_policy",
            "parental_agents",
            "rfc2317_prefix",
            "rfc2317_parent_managed",
            "registrar",
            "registry_domain_id",
            "expiration_date",
            "domain_status",
            "registrant",
            "admin_c",
            "tech_c",
            "billing_c",
            "tenant",
            "tags",
        )

    view = CSVModelChoiceField(
        queryset=View.objects.all(),
        required=False,
        to_field_name="name",
        error_messages={
            "invalid_choice": _("View %(value)s not found"),
        },
        label=_("View"),
    )
    status = CSVChoiceField(
        choices=ZoneStatusChoices,
        required=False,
        label=_("Status"),
    )
    nameservers = CSVModelMultipleChoiceField(
        queryset=NameServer.objects.all(),
        to_field_name="name",
        required=False,
        label=_("Nameservers"),
    )
    default_ttl = TimePeriodField(
        required=False,
        label=_("Default TTL"),
    )
    soa_ttl = TimePeriodField(
        required=False,
        help_text=_("TTL for the SOA record of the zone"),
        label=_("SOA TTL"),
    )
    soa_mname = CSVModelChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        to_field_name="name",
        error_messages={
            "invalid_choice": _("Nameserver %(value)s not found"),
        },
        help_text=_("Primary nameserver for the zone"),
        label=_("SOA MName"),
    )
    soa_rname = forms.CharField(
        required=False,
        help_text=_("Mailbox of the zone's administrator"),
        label=_("SOA RName"),
    )
    soa_serial_auto = forms.BooleanField(
        required=False,
        label=_("Generate SOA Serial"),
    )
    soa_serial = forms.IntegerField(
        required=False,
        label=_("SOA Serial"),
    )
    soa_refresh = TimePeriodField(
        required=False,
        help_text=_("Refresh interval for secondary nameservers"),
        label=_("SOA Refresh"),
    )
    soa_retry = TimePeriodField(
        required=False,
        help_text=_("Retry interval for secondary nameservers"),
        label=_("SOA Retry"),
    )
    soa_expire = TimePeriodField(
        required=False,
        help_text=_("Expire time after which the zone is considered unavailable"),
        label=_("SOA Expire"),
    )
    soa_minimum = TimePeriodField(
        required=False,
        help_text=_("Minimum TTL for negative results, e.g. NXRRSET, NXDOMAIN"),
        label=_("SOA Minimum TTL"),
    )
    rfc2317_prefix = RFC2317NetworkFormField(
        required=False,
        help_text=_("RFC2317 IPv4 prefix with a length of at least 25 bits"),
        label=_("RFC2317 Prefix"),
    )
    rfc2317_parent_managed = forms.BooleanField(
        required=False,
        help_text=_(
            "IPv4 reverse zone for delegating the RFC2317 PTR records is managed in NetBox DNS"
        ),
        label=_("RFC2317 Parent Managed"),
    )
    dnssec_policy = CSVModelChoiceField(
        queryset=DNSSECPolicy.objects.all(),
        required=False,
        to_field_name="name",
        error_messages={
            "invalid_choice": _("DNSSEC policy %(value)s not found"),
        },
        label=_("DNSSEC Policy"),
    )
    registrar = CSVModelChoiceField(
        queryset=Registrar.objects.all(),
        required=False,
        to_field_name="name",
        error_messages={
            "invalid_choice": _("Registrar %(value)s not found"),
        },
        label=_("Registrar"),
    )
    registry_domain_id = forms.CharField(
        required=False,
        label=_("Registry Domain ID"),
    )
    domain_status = CSVChoiceField(
        choices=ZoneEPPStatusChoices,
        required=False,
        label=_("Domain Status"),
    )
    registrant = CSVModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        to_field_name="contact_id",
        error_messages={
            "invalid_choice": _("Registrant contact ID %(value)s not found"),
        },
        label=_("Registrant"),
    )
    admin_c = CSVModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        to_field_name="contact_id",
        error_messages={
            "invalid_choice": _("Administrative contact ID %(value)s not found"),
        },
        label=_("Administrative Contact"),
    )
    tech_c = CSVModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        to_field_name="contact_id",
        error_messages={
            "invalid_choice": _("Technical contact ID %(value)s not found"),
        },
        label=_("Technical Contact"),
    )
    billing_c = CSVModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        to_field_name="contact_id",
        error_messages={
            "invalid_choice": _("Billing contact ID not found"),
        },
        label=_("Billing Contact"),
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Tenant"),
    )
    template = CSVModelChoiceField(
        queryset=ZoneTemplate.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Template"),
    )

    def clean_view(self):
        view = self.cleaned_data.get("view")
        if view is None:
            return View.get_default_view()

        return view

    def clean_nameservers(self):
        nameservers = self.cleaned_data.get("nameservers")
        zone_defaults = settings.PLUGINS_CONFIG.get("netbox_dns")

        if (
            self.data.get("nameservers") is None
            and zone_defaults.get("zone_nameservers") is not None
        ):
            nameservers = NameServer.objects.filter(
                name__in=zone_defaults.get("zone_nameservers")
            )

        return nameservers


class ZoneBulkEditForm(PrimaryModelBulkEditForm):
    model = Zone

    fieldsets = (
        FieldSet(
            "view",
            "status",
            "nameservers",
            "default_ttl",
            "description",
            name=_("Attributes"),
        ),
        FieldSet(
            "soa_ttl",
            "soa_mname",
            "soa_rname",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
            "soa_serial_auto",
            "soa_serial",
            name=_("SOA"),
        ),
        FieldSet(
            "dnssec_policy",
            "parental_agents",
            name=_("DNSSEC"),
        ),
        FieldSet(
            "rfc2317_prefix",
            "rfc2317_parent_managed",
            name=_("RFC2317"),
        ),
        FieldSet(
            "registrar",
            "registry_domain_id",
            "expiration_date",
            "domain_status",
            "registrant",
            "admin_c",
            "tech_c",
            "billing_c",
            name=_("Domain Registration"),
        ),
        FieldSet(
            "tenant_group",
            "tenant",
            name=_("Tenancy"),
        ),
    )

    nullable_fields = (
        "description",
        "nameservers",
        "rfc2317_prefix",
        "registrar",
        "expiration_date",
        "domain_status",
        "registry_domain_id",
        "registrant",
        "admin_c",
        "tech_c",
        "billing_c",
        "tenant",
        "comments",
    )

    view = DynamicModelChoiceField(
        queryset=View.objects.all(),
        required=False,
        label=_("View"),
    )
    status = forms.ChoiceField(
        choices=add_blank_choice(ZoneStatusChoices),
        required=False,
        label=_("Status"),
    )
    nameservers = DynamicModelMultipleChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        label=_("Nameservers"),
    )
    default_ttl = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("Default TTL"),
    )
    soa_ttl = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA TTL"),
    )
    soa_mname = DynamicModelChoiceField(
        queryset=NameServer.objects.all(),
        required=False,
        label=_("SOA MName"),
    )
    soa_rname = forms.CharField(
        required=False,
        label=_("SOA RName"),
    )
    soa_serial_auto = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
        label=_("Generate SOA Serial"),
    )
    soa_serial = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(1), MaxValueValidator(4294967295)],
        label=_("SOA Serial"),
    )
    soa_refresh = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA Refresh"),
    )
    soa_retry = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA Retry"),
    )
    soa_expire = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA Expire"),
    )
    soa_minimum = TimePeriodField(
        required=False,
        validators=[MinValueValidator(1)],
        label=_("SOA Minimum TTL"),
    )
    rfc2317_prefix = RFC2317NetworkFormField(
        required=False,
        validators=[validate_ipv4, validate_prefix, validate_rfc2317],
        help_text=_("RFC2317 IPv4 prefix with a length of at least 25 bits"),
        label=_("RFC2317 Prefix"),
    )
    rfc2317_parent_managed = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
        help_text=_(
            "IPv4 reverse zone for delegating the RFC2317 PTR records is managed in NetBox DNS"
        ),
        label=_("RFC2317 Parent Managed"),
    )
    dnssec_policy = DynamicModelChoiceField(
        queryset=DNSSECPolicy.objects.all(),
        required=False,
        label=_("DNSSEC Policy"),
    )
    parental_agents = SimpleArrayField(
        required=False,
        base_field=forms.GenericIPAddressField(),
        label=_("Parental Agents"),
    )
    registrar = DynamicModelChoiceField(
        queryset=Registrar.objects.all(),
        required=False,
        label=_("Registrar"),
    )
    registry_domain_id = forms.CharField(
        required=False,
        label=_("Registry Domain ID"),
    )
    expiration_date = forms.DateField(
        required=False,
        label=_("Expiration Date"),
        widget=DatePicker,
    )
    domain_status = forms.ChoiceField(
        choices=add_blank_choice(ZoneEPPStatusChoices),
        required=False,
        label=_("Domain Status"),
    )
    registrant = DynamicModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        label=_("Registrant"),
    )
    admin_c = DynamicModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        label=_("Administrative Contact"),
    )
    tech_c = DynamicModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        label=_("Technical Contact"),
    )
    billing_c = DynamicModelChoiceField(
        queryset=RegistrationContact.objects.all(),
        required=False,
        label=_("Billing Contact"),
    )
    tenant_group = DynamicModelChoiceField(
        queryset=TenantGroup.objects.all(),
        required=False,
        label=_("Tenant Group"),
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        label=_("Tenant"),
    )
