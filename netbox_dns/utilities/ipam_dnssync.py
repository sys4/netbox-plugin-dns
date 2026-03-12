import re

from collections import defaultdict

from dns import name as dns_name
from netaddr import IPNetwork

from django.conf import settings
from django.db.models import Q

from netbox.context import current_request
from ipam.models import IPAddress, Prefix

from netbox_dns.choices import RecordStatusChoices, RecordTypeChoices

from .dns import get_parent_zone_names
from .conversions import regex_from_list

__all__ = (
    "get_zones",
    "check_dns_records",
    "update_dns_records",
    "delete_dns_records",
    "get_views_by_prefix",
    "get_ip_addresses_by_prefix",
    "get_ip_addresses_by_view",
    "get_ip_addresses_by_zone",
    "check_record_permission",
    "get_query_from_filter",
    "check_filter",
    "get_cidr_address",
)


def _get_assigned_views(ip_address):
    address = get_cidr_address(ip_address)

    longest_prefix = Prefix.objects.filter(
        vrf=ip_address.vrf,
        prefix__net_contains_or_equals=address,
        netbox_dns_views__isnull=False,
    ).last()

    if longest_prefix is None:
        return []

    return longest_prefix.netbox_dns_views.all()


def _get_record_status(ip_address):
    return (
        RecordStatusChoices.STATUS_ACTIVE
        if ip_address.status
        in settings.PLUGINS_CONFIG["netbox_dns"].get(
            "dnssync_ipaddress_active_status", []
        )
        else RecordStatusChoices.STATUS_INACTIVE
    )


def _valid_entry(ip_address, zone):
    return zone.view in _get_assigned_views(ip_address) and dns_name.from_text(
        ip_address.dns_name
    ).is_subdomain(dns_name.from_text(zone.name))


def _match_data(ip_address, record):
    cf_disable_ptr = ip_address.custom_field_data.get(
        "ipaddress_dns_record_disable_ptr"
    )

    address = get_cidr_address(ip_address)

    return (
        record.fqdn.rstrip(".") == ip_address.dns_name.rstrip(".")
        and record.value == str(address.ip)
        and record.status == _get_record_status(ip_address)
        and record.ttl == ip_address.custom_field_data.get("ipaddress_dns_record_ttl")
        and (cf_disable_ptr is None or record.disable_ptr == cf_disable_ptr)
    )


def get_zones(ip_address, view=None, old_zone=None):
    from netbox_dns.models import Zone

    if view is None:
        views = _get_assigned_views(ip_address)
        if not views:
            return []

    else:
        views = [view]

    min_labels = settings.PLUGINS_CONFIG["netbox_dns"].get(
        "dnssync_minimum_zone_labels", 2
    )

    zones = Zone.objects.filter(
        view__in=views,
        name__iregex=regex_from_list(
            get_parent_zone_names(
                ip_address.dns_name, min_labels=min_labels, include_self=True
            )
        ),
        active=True,
    )

    zone_map = defaultdict(list)

    if old_zone is not None:
        zones = zones.exclude(pk=old_zone.pk)
        if _valid_entry(ip_address, old_zone):
            zone_map[old_zone.view].append(old_zone)

    for zone in zones:
        zone_map[zone.view].append(zone)

    return [
        sorted(zones_per_view, key=lambda x: len(x.name))[-1]
        for zones_per_view in zone_map.values()
    ]


def check_dns_records(ip_address, zone=None, view=None):
    from netbox_dns.models import Zone, Record

    if ip_address.dns_name == "":
        return

    if zone is None:
        zones = get_zones(ip_address, view=view)

        if not ip_address._state.adding:
            for record in ip_address.netbox_dns_records.filter(zone__in=zones):
                if not _match_data(ip_address, record):
                    updated = record.update_from_ip_address(ip_address)

                    if updated:
                        record.clean()

            zones = Zone.objects.filter(pk__in=[zone.pk for zone in zones]).exclude(
                pk__in=set(ip_address.netbox_dns_records.values_list("zone", flat=True))
            )

        for zone in zones:
            record = Record.create_from_ip_address(
                ip_address,
                zone,
            )

            if record is not None:
                record.clean()

    if ip_address._state.adding:
        return

    try:
        new_zone = get_zones(ip_address, old_zone=zone)[0]
    except IndexError:
        return

    for record in ip_address.netbox_dns_records.filter(zone=zone):
        updated = record.update_from_ip_address(ip_address, new_zone)

        if updated:
            record.clean(new_zone=new_zone)


def update_dns_records(ip_address, view=None, force=False):
    from netbox_dns.models import Zone, Record

    updated = False

    if ip_address.dns_name == "":
        return delete_dns_records(ip_address)

    zones = get_zones(ip_address, view=view)

    if not ip_address._state.adding:
        if view is None:
            address_records = ip_address.netbox_dns_records.all()
        else:
            address_records = ip_address.netbox_dns_records.filter(zone__view=view)

        for record in address_records:
            record.snapshot()

            if record.zone not in zones or ip_address.custom_field_data.get(
                "ipaddress_dns_disabled"
            ):
                record.delete()
                updated = True
                continue

            record.update_fqdn()
            updated, deleted = record.update_from_ip_address(ip_address)

            if deleted:
                record.delete()
                updated = True
            elif updated:
                record.save()
                updated = True

        zones = Zone.objects.filter(pk__in=[zone.pk for zone in zones]).exclude(
            pk__in=set(ip_address.netbox_dns_records.values_list("zone", flat=True))
        )

    for zone in zones:
        record = Record.create_from_ip_address(
            ip_address,
            zone,
        )

        if record is not None:
            record.save()
            updated = True

    return updated


def delete_dns_records(ip_address, view=None):
    from netbox_dns.models import Record

    if current_request.get() is None:
        address_records = ip_address.netbox_dns_records.all()
    else:
        # +
        # This is a dirty hack made necessary by NetBox grand idea of manipulating
        # objects in its event handling code, removing references to related objects
        # in pre_delete() before our pre_delete() handler has the chance to handle
        # them.
        #
        # TODO: Find something better. This is really awful.
        # -
        address = get_cidr_address(ip_address)
        address_records = Record.objects.filter(
            Q(
                Q(ipam_ip_address=ip_address)
                | Q(
                    type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA),
                    managed=True,
                    ip_address=address,
                    ipam_ip_address__isnull=True,
                )
            ),
        )

    if view is not None:
        address_records &= Record.objects.filter(zone__view=view)

    if not address_records.exists():
        return False

    for record in address_records:
        record.delete()

    return True


def get_views_by_prefix(prefix):
    from netbox_dns.models import View

    if (views := prefix.netbox_dns_views.all()).exists():
        return views

    if (parent := prefix.get_parents().filter(netbox_dns_views__isnull=False)).exists():
        return parent.last().netbox_dns_views.all()

    return View.objects.none()


def get_ip_addresses_by_prefix(prefix, check_view=True):
    """
    Find all IPAddress objects that are in a given prefix, provided that prefix
    is assigned to NetBox DNS view. IPAddress objects belonging to a sub-prefix
    that is assigned to a NetBox DNS view itself are excluded, because the zones
    that are relevant for them are depending on the view set of the sub-prefix.

    If neither the prefix nor any parent prefix is assigned to a view, the list
    of IPAddress objects returned is empty.
    """
    if check_view and not get_views_by_prefix(prefix):
        return IPAddress.objects.none()

    queryset = IPAddress.objects.filter(
        vrf=prefix.vrf, address__net_host_contained=prefix.prefix
    )

    for exclude_child in (
        prefix.get_children().filter(netbox_dns_views__isnull=False).distinct()
    ):
        queryset = queryset.exclude(
            vrf=exclude_child.vrf,
            address__net_host_contained=exclude_child.prefix,
        )

    return queryset


def get_ip_addresses_by_view(view):
    """
    Find all IPAddress objects that are within prefixes that have a NetBox DNS
    view assigned to them, or that inherit a view from their parent prefix.

    Inheritance is defined recursively if the prefix is assigned to the view or
    if it is a child prefix of the prefix that is not assigned to a view directly
    or by inheritance.
    """
    queryset = IPAddress.objects.none()
    for prefix in Prefix.objects.filter(netbox_dns_views__in=[view]):
        sub_queryset = IPAddress.objects.filter(
            vrf=prefix.vrf, address__net_host_contained=prefix.prefix
        )
        for exclude_child in prefix.get_children().exclude(
            Q(netbox_dns_views__isnull=True) | Q(netbox_dns_views__in=[view])
        ):
            sub_queryset = sub_queryset.exclude(
                vrf=exclude_child.vrf,
                address__net_host_contained=exclude_child.prefix,
            )
        queryset |= sub_queryset

    return queryset


def get_ip_addresses_by_zone(zone):
    """
    Find all IPAddress objects that are relevant for a NetBox DNS zone. These
    are the IPAddress objects in prefixes assigned to the same view, if the
    'dns_name' attribute of the IPAddress object ends in the zone's name.
    """
    queryset = get_ip_addresses_by_view(zone.view).filter(
        dns_name__regex=rf"\.{re.escape(zone.name)}\.?$"
    )

    return queryset


def check_record_permission(add=True, change=True, delete=True):
    checks = locals().copy()

    request = current_request.get()

    if request is None:
        return True

    return all(
        (
            request.user.has_perm(f"netbox_dns.{perm}_record")
            for perm, check in checks.items()
            if check
        )
    )


def get_query_from_filter(ip_address_filter):
    query = Q()

    if not isinstance(ip_address_filter, list):
        ip_address_filter = [ip_address_filter]

    for condition in ip_address_filter:
        if condition:
            query |= Q(**condition)
        else:
            return Q()

    return query


def check_filter(ip_address, ip_address_filter):
    query = get_query_from_filter(ip_address_filter)
    against = ip_address._get_field_expression_map(meta=IPAddress._meta)

    return query.check(against)


def get_cidr_address(ip_address):
    # +
    # Always return an IPNetwork object, regardless if the address field is a
    # string or an IPNetwork object.
    #
    # This is required because an IPAddress may have a string in that field
    # if it has not been retrieved from the database.
    # -
    if type(ip_address.address) is str:
        return IPNetwork(ip_address.address)
    else:
        return ip_address.address
