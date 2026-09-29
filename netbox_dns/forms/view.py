from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from ipam.models import Prefix
from netbox.context import current_request
from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
    PrimaryModelImportForm,
)
from netbox_dns.fields import PrefixDynamicModelMultipleChoiceField
from netbox_dns.models import View
from netbox_dns.utilities import (
    check_dns_records,
    get_ip_addresses_by_prefix,
    get_views_by_prefix,
    validate_ip_address_filter,
)
from tenancy.forms import TenancyFilterForm, TenancyForm
from tenancy.models import Tenant, TenantGroup
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import (
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    JSONField,
    TagFilterField,
)
from utilities.forms.rendering import FieldSet

__all__ = (
    "ViewForm",
    "ViewFilterForm",
    "ViewImportForm",
    "ViewBulkEditForm",
    "ViewPrefixEditForm",
)


class ViewPrefixUpdateMixin:
    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        if self.instance._state.adding or "prefixes" not in self.changed_data:
            return

        prefixes = self.cleaned_data.get("prefixes")
        old_prefixes = View.objects.get(pk=self.instance.pk).prefixes.all()

        for prefix in prefixes.difference(old_prefixes):
            for ip_address in get_ip_addresses_by_prefix(prefix, check_view=False):
                try:
                    check_dns_records(ip_address, view=self.instance)
                except ValidationError as exc:
                    self.add_error("prefixes", exc.messages)

        # +
        # Determine the prefixes that, when removed from the view, have no direct view
        # assignment left. These prefixes will potentially inherit from a different view,
        # which means that they have to be validated against different zones.
        # -
        check_prefixes = set(
            old_prefixes.annotate(view_count=Count("netbox_dns_views")).filter(
                Q(view_count=1, netbox_dns_views=self.instance)
                | Q(netbox_dns_views__isnull=True)
            )
        ) - set(prefixes)

        for check_prefix in check_prefixes:
            # +
            # Check whether the prefix will get a new view by inheritance from its
            # parent. If that's the case, the IP addresses need to be checked.
            # -
            if (parent := check_prefix.get_parents().last()) is None:
                continue

            for view in get_views_by_prefix(parent):
                if view == self.instance:
                    continue

                for ip_address in get_ip_addresses_by_prefix(
                    check_prefix, check_view=False
                ):
                    try:
                        check_dns_records(ip_address, view=view)
                    except ValidationError as exc:
                        self.add_error("prefixes", exc.messages)


class ViewForm(ViewPrefixUpdateMixin, TenancyForm, PrimaryModelForm):
    class Meta:
        model = View

        fields = (
            "name",
            "description",
            "owner",
            "comments",
            "default_view",
            "prefixes",
            "ip_address_filter",
            "tenant_group",
            "tenant",
            "tags",
        )

    fieldsets = (
        FieldSet(
            "name",
            "description",
            "default_view",
            name=_("View"),
        ),
        FieldSet(
            "prefixes",
            "ip_address_filter",
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

        if settings.PLUGINS_CONFIG["netbox_dns"].get("dnssync_disabled"):
            del self.fields["prefixes"]
            del self.fields["ip_address_filter"]

        if request := current_request.get():
            if not request.user.has_perm("ipam.view_prefix"):
                self._saved_prefixes = self.initial["prefixes"]
                self.initial["prefixes"] = []
                self.fields["prefixes"].disabled = True
                self.fields["prefixes"].widget.attrs["placeholder"] = _(
                    "You do not have permission to modify assigned prefixes"
                )

    prefixes = PrefixDynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        context={
            "depth": None,
        },
        label=_("IPAM Prefixes"),
    )
    ip_address_filter = JSONField(
        required=False,
        help_text=_("Specify criteria for address record creation in JSON form"),
        label=_("IP Address Filter"),
    )

    def clean_prefixes(self):
        if hasattr(self, "_saved_prefixes"):
            return self._saved_prefixes

        return self.cleaned_data["prefixes"]

    def clean_ip_address_filter(self):
        ip_address_filter = self.cleaned_data.get("ip_address_filter")

        try:
            validate_ip_address_filter(ip_address_filter)
        except ValidationError as exc:
            self.add_error("ip_address_filter", exc)

        return ip_address_filter


class ViewFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = View

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
            "default_view",
            name=_("Attributes"),
        ),
        FieldSet(
            "prefix_id",
        ),
        FieldSet(
            "tenant_group_id",
            "tenant_id",
            name=_("Tenancy"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if settings.PLUGINS_CONFIG["netbox_dns"].get("dnssync_disabled"):
            del self.fields["prefix_id"]

    name = forms.CharField(
        required=False,
        label=_("Name"),
    )
    description = forms.CharField(
        required=False,
        label=_("Description"),
    )
    default_view = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
        label=_("Default View"),
    )
    prefix_id = PrefixDynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        context={
            "depth": None,
        },
        label=_("Prefix"),
    )
    tag = TagFilterField(model)


class ViewImportForm(ViewPrefixUpdateMixin, PrimaryModelImportForm):
    class Meta:
        model = View

        fields = (
            "name",
            "description",
            "owner",
            "comments",
            "prefixes",
            "tenant",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if settings.PLUGINS_CONFIG["netbox_dns"].get("dnssync_disabled"):
            del self.fields["prefixes"]

    prefixes = CSVModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        help_text=_("Prefix IDs assigned to the view"),
        label=_("Prefixes"),
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        label=_("Tenant"),
    )


class ViewBulkEditForm(PrimaryModelBulkEditForm):
    model = View

    fieldsets = (
        FieldSet(
            "description",
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
        "tenant",
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


class ViewPrefixEditForm(forms.ModelForm):
    class Meta:
        model = Prefix

        fields = ("views",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.initial["views"] = self.instance.netbox_dns_views.all()
        self._permission_denied = False

        if request := current_request.get():
            if not request.user.has_perm("netbox_dns.change_view"):
                self._permission_denied = True
                self.initial["views"] = []
                self.fields["views"].disabled = True
                self.fields["views"].widget.attrs["placeholder"] = _(
                    "You do not have permission to modify assigned views"
                )

    views = DynamicModelMultipleChoiceField(
        queryset=View.objects.all(),
        required=False,
        help_text=_(
            "Explicitly assigning DNS views overrides all inherited views for this prefix"
        ),
        label=_("Assigned DNS Views"),
    )

    def clean(self, *args, **kwargs):
        if self._permission_denied:
            return

        prefix = self.instance

        super().clean(*args, **kwargs)

        views = self.cleaned_data.get("views")
        old_views = prefix.netbox_dns_views.all()

        check_views = View.objects.none()

        if not views.exists():
            if (parent := prefix.get_parents().last()) is not None:
                check_views = parent.netbox_dns_views.difference(old_views)

        else:
            check_views = views.difference(old_views)

        for view in check_views:
            try:
                for ip_address in get_ip_addresses_by_prefix(prefix, check_view=False):
                    check_dns_records(ip_address, view=view)
            except ValidationError as exc:
                self.add_error("views", exc.messages)

    def save(self, *args, **kwargs):
        prefix = self.instance

        if self._permission_denied:
            return prefix

        # +
        # TODO: Workaround for Django 6.1 difference() failing with ordered models:
        #
        # * Added an empty order_by()
        #
        # see https://github.com/django/django/pull/21798
        # -
        old_views = prefix.netbox_dns_views.order_by()
        views = self.cleaned_data.get("views").order_by()

        for view in views.difference(old_views):
            view.prefixes.add(prefix)
        for view in old_views.difference(views):
            view.prefixes.remove(prefix)

        return prefix
