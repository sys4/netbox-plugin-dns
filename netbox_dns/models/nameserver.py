from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from dns import name as dns_name

from netbox.models import PrimaryModel
from netbox.models.features import ContactsMixin
from netbox.plugins.utils import get_plugin_config
from netbox.search import SearchIndex, register_search
from netbox_dns.branching import dns_branch_replay_active
from netbox_dns.choices import RecordTypeChoices
from netbox_dns.mixins import ObjectModificationMixin
from netbox_dns.utilities import (
    NameFormatError,
    name_to_unicode,
    normalize_name,
)
from netbox_dns.validators import validate_fqdn

__all__ = (
    "NameServer",
    "NameServerIndex",
)


class NameServer(ObjectModificationMixin, ContactsMixin, PrimaryModel):
    class Meta:
        verbose_name = _("Nameserver")
        verbose_name_plural = _("Nameservers")

        ordering = ("name",)

        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="name_unique_ci",
                violation_error_message=_(
                    "There is already a nameserver with this name"
                ),
            ),
        ]

    clone_fields = (
        "name",
        "description",
        "tenant",
    )

    def __str__(self):
        try:
            return dns_name.from_text(self.name, origin=None).to_unicode()
        except dns_name.IDNAException:
            return self.name

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        db_collation="natural_sort",
    )
    tenant = models.ForeignKey(
        verbose_name=_("Tenant"),
        to="tenancy.Tenant",
        on_delete=models.PROTECT,
        related_name="netbox_dns_nameservers",
        blank=True,
        null=True,
    )

    @property
    def display_name(self):
        return name_to_unicode(self.name)

    def clean_fields(self, exclude=None):
        if dns_branch_replay_active():
            super().clean_fields(exclude=exclude)
            return

        if get_plugin_config("netbox_dns", "convert_names_to_lowercase", False):
            self.name = self.name.lower()

        super().clean_fields(exclude=exclude)

    clean_fields.alters_data = True

    def clean(self, *args, **kwargs):
        if dns_branch_replay_active():
            # See save(): the name is already normalised/validated in the
            # branch; skip model-level validation during a merge/sync/revert
            # replay.
            return

        try:
            self.name = normalize_name(self.name)
        except NameFormatError as exc:
            raise ValidationError(
                {
                    "name": str(exc),
                }
            )

        try:
            validate_fqdn(self.name)
        except ValidationError as exc:
            raise ValidationError(
                {
                    "name": exc,
                }
            )

        super().clean(*args, **kwargs)

    clean.alters_data = True

    def save(self, *args, **kwargs):
        if dns_branch_replay_active():
            # Replaying a NetBox Branching merge/sync/revert: persist the row
            # only. The dependent zones' SOA/NS record updates are replayed
            # from the branch changelog. See netbox_dns.branching.
            super().save(*args, **kwargs)
            return

        self.full_clean()

        changed_fields = self.changed_fields

        with transaction.atomic():
            super().save(*args, **kwargs)

            if changed_fields is not None and "name" in changed_fields:
                soa_zones = self.soa_zones.all()
                for soa_zone in soa_zones:
                    soa_zone.update_soa_record()

                zones = self.zones.all()
                for zone in zones:
                    zone.update_ns_records()

    def delete(self, *args, **kwargs):
        if dns_branch_replay_active():
            # See save(): the managed NS record cleanup is replayed from the
            # branch changelog, so drop the row only.
            super().delete(*args, **kwargs)
            return

        with transaction.atomic():
            for zone in self.zones.all():
                zone.records.filter(
                    Q(managed=True),
                    Q(value=f"{self.name}."),
                    Q(type=RecordTypeChoices.NS),
                ).delete()

            super().delete(*args, **kwargs)


@register_search
class NameServerIndex(SearchIndex):
    model = NameServer

    fields = (
        ("name", 100),
        ("description", 500),
    )
