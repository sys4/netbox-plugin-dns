from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ImproperlyConfigured

from netbox.plugins import PluginConfig
from netbox.plugins.utils import get_plugin_config

__version__ = "1.5.2"


def _check_list(setting):
    if not isinstance(get_plugin_config("netbox_dns", setting), list):
        raise ImproperlyConfigured(f"{setting} must be a list")


class DNSConfig(PluginConfig):
    name = "netbox_dns"
    verbose_name = _("NetBox DNS")
    description = _("NetBox plugin for DNS data")
    min_version = "4.5.0"
    version = __version__
    author = "Peter Eckel"
    author_email = "pete@netbox-dns.org"
    required_settings = []
    default_settings = {
        "zone_default_ttl": 86400,
        "zone_soa_ttl": 86400,
        "zone_soa_serial": 1,
        "zone_soa_refresh": 43200,
        "zone_soa_retry": 7200,
        "zone_soa_expire": 2419200,
        "zone_soa_minimum": 3600,
        "zone_active_status": ["active", "dynamic"],
        "zone_expiration_warning_days": 30,
        "filter_record_types": [
            # Obsolete or experimental RRTypes
            "A6",  # RFC 6563: Historic
            "AFSDB",  # RFC 5864: Obsolete
            "APL",  # RFC 3123: Experimental
            "AVC",  # https://www.iana.org/assignments/dns-parameters/AVC/avc-completed-template
            "GPOS",  # RFC 1712: Experimental
            "KEY",  # RFC 3755: Obsolete
            "L32",  # RFC 6742: Experimental
            "L64",  # RFC 6742: Experimental
            "LP",  # RFC 6742: Experimental
            "MB",  # RFC 2505: Unlikely to ever be adopted
            "MD",  # RFC 973: Obsolete
            "MF",  # RFC 973: Obsolete
            "MG",  # RFC 2505: Unlikely to ever be adopted
            "MINFO",  # RFC 2505: Unlikely to ever be adopted
            "MR",  # RFC 2505: Unlikely to ever be adopted
            "NID",  # RFC 6742: Experimental
            "NINFO",  # Application expired
            "NULL",  # RFC 1035: Obsolete
            "NXT",  # RFC 3755: Obsolete
            "SIG",  # RFC 3755: Obsolete
            "SPF",  # RFC 7208: Obsolete
            "WKS",  # RFC 1127: Not recommended
            # RRTypes with no current use by any notable application
            # (see https://en.wikipedia.org/wiki/List_of_DNS_record_types)
            "RP",
            "ISDN",
            "RT",
            "X25",
            "NSAP",
            "NSAP_PTR",
            "PX",
            "TYPE0",  # Reserved
            "UNSPEC",  # Reserved
            # DNSSEC RRTypes that are usually not manually maintained
            "NSEC",
            "NSEC3",
            "RRSIG",
        ],
        "filter_record_types+": [],
        "filter_record_types-": [],
        "custom_record_types": [],
        "record_active_status": ["active"],
        "dnssync_disabled": False,
        "dnssync_ipaddress_active_status": ["active", "dhcp", "slaac"],
        "dnssync_conflict_deactivate": False,
        "dnssync_minimum_zone_labels": 2,
        "tolerate_characters_in_zone_labels": "",
        "tolerate_underscores_in_labels": False,
        "tolerate_leading_underscore_types": [
            "CNAME",
            "DNAME",
            "SRV",
            "SVCB",
            "TLSA",
            "TXT",
        ],
        "tolerate_non_rfc1035_types": [],
        "enable_root_zones": False,
        "enforce_unique_records": True,
        "enforce_unique_rrset_ttl": True,
        "enforce_zone_cut_checking": True,
        "menu_name": "DNS",
        "top_level_menu": True,
        "convert_names_to_lowercase": False,
        "dnssec_purge_keys": 7776000,  # P90D
        "dnssec_publish_safety": 3600,  # PT1H
        "dnssec_retire_safety": 3600,  # PT1H
        "dnssec_signatures_jitter": 43200,  # PT12H
        "dnssec_signatures_refresh": 432000,  # P5D
        "dnssec_signatures_validity": 1209600,  # P14D
        "dnssec_signatures_validity_dnskey": 1209600,  # P14D
        "dnssec_max_zone_ttl": 86400,  # P1D
        "dnssec_zone_propagation_delay": 300,  # PT5M
        "dnssec_parent_ds_ttl": 86400,  # P1D
        "dnssec_parent_propagation_delay": 3600,  # PT1H
        "dnssec_dnskey_ttl": 3600,  # PT1H
    }
    base_url = "netbox-dns"

    def ready(self):
        super().ready()

        import netbox_dns.signals.dnssec  # noqa: F401

        if not get_plugin_config("netbox_dns", "dnssync_disabled"):
            import netbox_dns.signals.ipam_dnssync  # noqa: F401
            import netbox_dns.tables.ipam_dnssync  # noqa: F401

        for setting in (
            "zone_active_status",
            "record_active_status",
            "dnssync_ipaddress_active_status",
            "tolerate_leading_underscore_types",
            "filter_record_types",
            "filter_record_types+",
            "custom_record_types",
        ):
            _check_list(setting)


#
# Initialize plugin config
#
config = DNSConfig
