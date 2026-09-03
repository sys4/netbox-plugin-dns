from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = (
    "RegistrationContact",
    "RegistrationContactIndex",
)


class RegistrationContact(PrimaryModel):
    class Meta:
        verbose_name = _("Registration Contact")
        verbose_name_plural = _("Registration Contacts")

        ordering = (
            "name",
            "contact_id",
        )

    clone_fields = (
        "name",
        "description",
        "organization",
        "street",
        "city",
        "state_province",
        "postal_code",
        "country",
        "phone",
        "phone_ext",
        "fax",
        "fax_ext",
        "email",
        "tags",
    )

    def __str__(self):
        if self.name is not None:
            return f"{self.contact_id} ({self.name})"

        return self.contact_id

    # +
    # Data fields according to https://www.icann.org/resources/pages/rdds-labeling-policy-2017-02-01-en
    # -
    contact_id = models.CharField(
        verbose_name=_("Contact ID"),
        max_length=50,
        unique=True,
        db_collation="natural_sort",
    )
    name = models.CharField(
        verbose_name=_("Name"),
        blank=True,
        max_length=100,
        db_collation="natural_sort",
    )
    organization = models.CharField(
        verbose_name=_("Organization"),
        blank=True,
        max_length=200,
    )
    street = models.CharField(
        verbose_name=_("Street"),
        blank=True,
        max_length=255,
    )
    city = models.CharField(
        verbose_name=_("City"),
        blank=True,
        max_length=50,
    )
    state_province = models.CharField(
        verbose_name=_("State/Province"),
        blank=True,
        max_length=255,
    )
    postal_code = models.CharField(
        verbose_name=_("Postal Code"),
        blank=True,
        max_length=20,
    )
    country = models.CharField(
        verbose_name=_("Country (ISO 3166)"),
        blank=True,
        max_length=2,
    )
    phone = models.CharField(
        verbose_name=_("Phone"),
        blank=True,
        max_length=50,
    )
    phone_ext = models.CharField(
        verbose_name=_("Phone Extension"),
        blank=True,
        max_length=50,
    )
    fax = models.CharField(
        verbose_name=_("Fax"),
        blank=True,
        max_length=50,
    )
    fax_ext = models.CharField(
        verbose_name=_("Fax Extension"),
        blank=True,
        max_length=50,
    )
    email = models.EmailField(
        verbose_name=_("Email"),
        blank=True,
    )

    @property
    def zones(self):
        return (
            set(self.registrant_zones.all())
            | set(self.admin_c_zones.all())
            | set(self.tech_c_zones.all())
            | set(self.billing_c_zones.all())
        )


@register_search
class RegistrationContactIndex(SearchIndex):
    model = RegistrationContact

    fields = (
        ("name", 100),
        ("contact_id", 100),
        ("email", 200),
        ("organization", 500),
        ("description", 500),
    )
