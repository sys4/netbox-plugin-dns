from netaddr import IPNetwork

from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import pre_delete, pre_save, post_save, m2m_changed
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from netbox.context import current_request
from netbox.signals import post_clean
from ipam.models import IPAddress, Prefix
from utilities.exceptions import AbortRequest

from netbox_dns.utilities import (
    check_dns_records,
    check_record_permission,
    update_dns_records,
    delete_dns_records,
    get_views_by_prefix,
    get_ip_addresses_by_prefix,
)

DNSSYNC_CUSTOM_FIELDS = {
    "ipaddress_dns_disabled": False,
    "ipaddress_dns_record_ttl": None,
    "ipaddress_dns_record_disable_ptr": False,
}

IPADDRESS_ACTIVE_STATUS = settings.PLUGINS_CONFIG["netbox_dns"][
    "dnssync_ipaddress_active_status"
]
ENFORCE_UNIQUE_RECORDS = settings.PLUGINS_CONFIG["netbox_dns"]["enforce_unique_records"]


@receiver(post_clean, sender=IPAddress)
def ipam_dnssync_ipaddress_post_clean(instance, **kwargs):
    if not instance.dns_name:
        return

    if not isinstance(instance.address, IPNetwork):
        return

    if instance.custom_field_data.get("ipaddress_dns_disabled"):
        return

    # +
    # Check for uniqueness of IP address and dns_name. If unique records are
    # enforced, report an error when trying to create the same IP address with
    # the same dns_name. Ignore existing IP addresses that have their CF
    # "ipaddress_dns_disabled" set to "True".
    # -
    duplicate_addresses = IPAddress.objects.filter(
        address=instance.address,
        vrf=instance.vrf,
        dns_name=instance.dns_name,
        status__in=IPADDRESS_ACTIVE_STATUS,
    )
    if not instance._state.adding:
        duplicate_addresses = duplicate_addresses.exclude(pk=instance.pk)

    if ENFORCE_UNIQUE_RECORDS and instance.status in IPADDRESS_ACTIVE_STATUS:
        for ip_address in duplicate_addresses.only("custom_field_data"):
            if not ip_address.custom_field_data.get("ipaddress_dns_disabled"):
                raise ValidationError(
                    {
                        "dns_name": _(
                            "Unique DNS records are enforced and there is already "
                            "an active IP address {address} with DNS name {name}. Please choose "
                            "a different name or disable record creation for this IP address."
                        ).format(address=instance.address, name=instance.dns_name)
                    }
                )

    # +
    # Check NetBox DNS record permission for changes to IPAddress custom fields
    # -
    if (current_request.get()) is not None:
        cf_data = instance.custom_field_data
        if (
            not instance._state.adding
            and any(
                (
                    cf_data.get(cf, cf_default)
                    != IPAddress.objects.get(pk=instance.pk).custom_field_data.get(
                        cf, cf_default
                    )
                    for cf, cf_default in DNSSYNC_CUSTOM_FIELDS.items()
                )
            )
            and not check_record_permission()
        ) or (
            instance._state.adding
            and any(
                (
                    cf_data.get(cf, cf_default) != cf_default
                    for cf, cf_default in DNSSYNC_CUSTOM_FIELDS.items()
                )
            )
            and not check_record_permission(change=False, delete=False)
        ):
            raise ValidationError(
                _("You do not have permission to alter DNSsync custom fields")
            )

    try:
        check_dns_records(instance)
    except ValidationError as exc:
        raise ValidationError({"dns_name": exc.messages})


@receiver(pre_delete, sender=IPAddress)
def ipam_dnssync_ipaddress_pre_delete(instance, **kwargs):
    delete_dns_records(instance)


@receiver(pre_save, sender=IPAddress)
def ipam_dnssync_ipaddress_pre_save(instance, **kwargs):
    check_dns_records(instance)


@receiver(post_save, sender=IPAddress)
def ipam_dnssync_ipaddress_post_save(instance, **kwargs):
    instance.refresh_from_db()
    update_dns_records(instance)


@receiver(pre_save, sender=Prefix)
def ipam_dnssync_prefix_pre_save(instance, **kwargs):
    """
    Changes that modify the prefix hierarchy cannot be validated properly before
    commiting them. So the solution in this case is to ask the user to deassign
    the prefix from any views it is assigned to and retry.
    """
    request = current_request.get()

    if instance._state.adding or not instance.netbox_dns_views.exists():
        return

    saved_prefix = Prefix.objects.prefetch_related("netbox_dns_views").get(
        pk=instance.pk
    )
    if saved_prefix.prefix != instance.prefix or saved_prefix.vrf != instance.vrf:
        dns_views = ", ".join([view.name for view in instance.netbox_dns_views.all()])
        if request is not None:
            raise AbortRequest(
                _(
                    "This prefix is currently assigned to the following DNS views: {views}. "
                    "Please deassign it from these views before making changes to the prefix "
                    "or VRF."
                ).format(views=dns_views)
            )

        raise ValidationError(
            _(
                "Prefix is assigned to DNS views {views}. Prefix and VRF must not be changed"
            ).format(views=dns_views)
        )


@receiver(pre_delete, sender=Prefix)
def ipam_dnssync_prefix_pre_delete(instance, **kwargs):
    parent = instance.get_parents().last()
    request = current_request.get()

    if parent is not None and get_views_by_prefix(instance) != get_views_by_prefix(
        parent
    ):
        try:
            for prefix in instance.get_children().filter(
                _depth=instance.depth + 1, netbox_dns_views__isnull=True
            ):
                for ip_address in get_ip_addresses_by_prefix(prefix):
                    check_dns_records(ip_address)
        except ValidationError as exc:
            if request is not None:
                raise AbortRequest(
                    _(
                        "Prefix deletion would cause DNS errors: {errors}. Please review "
                        "DNS View assignments for this and the parent prefix"
                    ).format(errors=exc.messages[0])
                )
            else:
                raise exc

    # +
    # CAUTION: This only works because the NetBox workaround for an ancient
    # Django bug (see https://code.djangoproject.com/ticket/17688) has already
    # removed the relations between the prefix and the views when this signal
    # handler runs.
    #
    # Should anything be fixed, this code will stop working and need to be
    # revisited.
    #
    # The NetBox workaround only works for requests, not for model level
    # operations. The following code replicates it for non-requests.
    # -
    if request is None:
        for view in instance.netbox_dns_views.all():
            view.snapshot()
            view.prefixes.remove(instance)

    for ip_address in get_ip_addresses_by_prefix(instance):
        update_dns_records(ip_address)


@receiver(m2m_changed, sender=Prefix.netbox_dns_views.through)
def ipam_dnssync_view_prefix_changed(**kwargs):
    action = kwargs.get("action")

    check_view = action != "post_remove"

    ip_addresses = IPAddress.objects.none()
    for prefix in Prefix.objects.filter(pk__in=kwargs.get("pk_set")):
        ip_addresses |= get_ip_addresses_by_prefix(prefix, check_view=check_view)

    for ip_address in ip_addresses.distinct():
        update_dns_records(ip_address)
