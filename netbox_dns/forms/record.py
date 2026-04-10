from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    DynamicModelMultipleChoiceField,
    TagFilterField,
    CSVChoiceField,
    CSVModelChoiceField,
    DynamicModelChoiceField,
)
from utilities.forms.widgets import BulkEditNullBooleanSelect
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES, add_blank_choice
from utilities.forms.rendering import FieldSet
from tenancy.models import Tenant, TenantGroup
from tenancy.forms import TenancyForm, TenancyFilterForm

from netbox_dns.models import View, Zone, Record
from netbox_dns.choices import RecordSelectableTypeChoices, RecordStatusChoices
from netbox_dns.utilities import name_to_unicode
from netbox_dns.fields import TimePeriodField

__all__ = (
    "RecordForm",
    "RecordFilterForm",
    "RecordImportForm",
    "RecordBulkEditForm",
)


class RecordForm(TenancyForm, PrimaryModelForm):
    class Meta:
        model = Record

        fields = (
            "name",
            "description",
            "owner",
            "comments",
            "zone",
            "type",
            "value",
            "status",
            "ttl",
            "disable_ptr",
            "tenant_group",
            "tenant",
            "tags",
        )

        labels = {
            "disable_ptr": _("Disable PTR"),
            "ttl": _("TTL"),
        }

    fieldsets = (
        FieldSet(
            "name",
            "description",
            "view",
            "zone",
            "type",
            "value",
            "status",
            "ttl",
            "disable_ptr",
            name=_("Record"),
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

    view = DynamicModelChoiceField(
        queryset=View.objects.all(),
        required=False,
        initial_params={
            "zones": "$zone",
        },
        label=_("View"),
    )
    zone = DynamicModelChoiceField(
        queryset=Zone.objects.all(),
        required=True,
        query_params={
            "view_id": "$view",
        },
        label=_("Zone"),
    )
    type = forms.ChoiceField(
        choices=add_blank_choice(RecordSelectableTypeChoices),
        required=True,
        label=_("Type"),
    )
    ttl = TimePeriodField(
        required=False,
        label=_("TTL"),
    )


class RecordFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = Record

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
            "zone_id",
            "fqdn",
            "type",
            "value",
            "status",
            "ttl",
            "disable_ptr",
            "active",
            name=_("Attributes"),
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
    fqdn = forms.CharField(
        required=False,
        label=_("FQDN"),
    )
    type = forms.MultipleChoiceField(
        choices=RecordSelectableTypeChoices,
        required=False,
        label=_("Type"),
    )
    value = forms.CharField(
        required=False,
        label=_("Value"),
    )
    disable_ptr = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Disable PTR"),
    )
    status = forms.MultipleChoiceField(
        choices=RecordStatusChoices,
        required=False,
        label=_("Status"),
    )
    ttl = TimePeriodField(
        required=False,
        label=_("TTL"),
    )
    view_id = DynamicModelMultipleChoiceField(
        queryset=View.objects.all(),
        required=False,
        label=_("View"),
    )
    zone_id = DynamicModelMultipleChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        label=_("Zone"),
        query_params={
            "view_id": "$view_id",
        },
    )
    active = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Active"),
    )
    tag = TagFilterField(model)


class RecordImportForm(PrimaryModelImportForm):
    class Meta:
        model = Record

        fields = (
            "name",
            "description",
            "owner",
            "comments",
            "zone",
            "view",
            "type",
            "value",
            "ttl",
            "disable_ptr",
            "tenant",
            "tags",
        )

        labels = {
            "disable_ptr": _("Disable PTR"),
            "ttl": _("TTL"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        view = None
        if self.is_bound and "view" in self.data:
            try:
                view = self.fields["view"].to_python(self.data["view"])
            except forms.ValidationError:
                pass

        if view is not None:
            self.fields["zone"].queryset = view.zones
        else:
            self.fields["zone"].queryset = View.get_default_view().zones

    zone = CSVModelChoiceField(
        queryset=Zone.objects.all(),
        to_field_name="name",
        required=True,
        label=_("Zone"),
        error_messages={
            "invalid_choice": _("Zone %(value)s not found"),
        },
    )
    view = CSVModelChoiceField(
        queryset=View.objects.all(),
        to_field_name="name",
        required=False,
        label=_("View"),
        error_messages={
            "invalid_choice": _("View %(value)s not found"),
        },
        help_text=_("This field is required if the zone is not in the default view"),
    )
    type = CSVChoiceField(
        choices=RecordSelectableTypeChoices,
        required=True,
        label=_("Type"),
    )
    status = CSVChoiceField(
        choices=RecordStatusChoices,
        required=False,
        label=_("Status"),
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        label=_("Tenant"),
    )

    def is_valid(self):
        try:
            is_valid = super().is_valid()
        except Record.zone.RelatedObjectDoesNotExist:
            is_valid = False

        return is_valid


class RecordBulkEditForm(PrimaryModelBulkEditForm):
    model = Record

    fieldsets = (
        FieldSet(
            "description",
            "zone",
            "type",
            "value",
            "status",
            "ttl",
            "disable_ptr",
            name=_("Attributes"),
        ),
        FieldSet(
            "tenant_group",
            "tenant",
            name=_("Tenancy"),
        ),
    )

    nullable_fields = (
        "description",
        "ttl",
        "tenant",
    )

    zone = DynamicModelChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        label=_("Zone"),
    )
    type = forms.ChoiceField(
        choices=add_blank_choice(RecordSelectableTypeChoices),
        required=False,
        label=_("Type"),
    )
    value = forms.CharField(
        required=False,
        label=_("Value"),
    )
    status = forms.ChoiceField(
        choices=add_blank_choice(RecordStatusChoices),
        required=False,
        label=_("Status"),
    )
    ttl = TimePeriodField(
        required=False,
        label=_("TTL"),
    )
    disable_ptr = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
        label=_("Disable PTR"),
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
