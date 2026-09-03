from django.core.management.base import BaseCommand
from netaddr import IPAddress

from netbox.plugins.utils import get_plugin_config
from netbox_dns.choices import RecordTypeChoices
from netbox_dns.models import Record, Zone

ZONE_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "zone_active_status")


class Command(BaseCommand):
    help = "Clean up NetBox DNS database"

    def handle(self, *model_names, **options):
        self._zone_cleanup_ns_records(**options)
        self._zone_cleanup_soa_records(**options)
        self._zone_update_arpa_network(**options)
        self._record_cleanup_disable_ptr(**options)
        self._record_update_ptr_records(**options)
        self._record_update_ip_address(**options)
        self._record_remove_orphaned_ptr_records(**options)
        self._record_remove_orphaned_address_records(**options)
        self._record_remove_ptr_records_from_inactive_zones(**options)

        if options.get("verbosity"):
            self.stdout.write("Database cleanup completed.")

    def _zone_cleanup_ns_records(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Cleaning up the NS records for all zones")

        ns_name = "@"

        for zone in Zone.objects.all():
            nameservers = zone.nameservers.all()
            nameserver_names = [f"{ns.name.rstrip('.')}." for ns in nameservers]

            delete_ns = zone.records.filter(
                name=ns_name, type=RecordTypeChoices.NS
            ).exclude(value__in=nameserver_names)
            for record in delete_ns:
                if options.get("verbosity") > 1:
                    self.stdout.write(
                        f"Removing obsolete NS record '{record}' with value '{record.value}'"
                    )
                record.delete()

            for ns in nameserver_names:
                ns_records = zone.records.filter(
                    name=ns_name,
                    type=RecordTypeChoices.NS,
                    value=ns,
                )

                delete_ns = ns_records[1:]
                for record in delete_ns:
                    if options.get("verbosity") > 1:
                        self.stdout.write(
                            f"Removing duplicate NS record '{record}' with value '{record.value}'"
                        )
                    record.delete()

                try:
                    ns_record = zone.records.get(
                        name=ns_name,
                        type=RecordTypeChoices.NS,
                        value=ns,
                    )

                    if ns_record.ttl is not None or not ns_record.managed:
                        if options.get("verbosity") > 1:
                            self.stdout.write(
                                f"Updating NS record '{ns_record}' with value '{record.value}'"
                            )
                        ns_record.ttl = None
                        ns_record.managed = True
                        ns_record.save()

                except Record.DoesNotExist:
                    if options.get("verbosity") > 1:
                        self.stdout.write(
                            f"Creating NS record for '{ns.rstrip('.')}' in zone '{zone}'"
                        )
                    Record.objects.create(
                        name=ns_name,
                        zone=zone,
                        type=RecordTypeChoices.NS,
                        value=ns,
                        ttl=None,
                        managed=True,
                    )

    def _zone_cleanup_soa_records(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Cleaning up the SOA record for all zones")

        soa_name = "@"

        for zone in Zone.objects.all():
            delete_soa = zone.records.filter(name=soa_name, type=RecordTypeChoices.SOA)[
                1:
            ]
            for record in delete_soa:
                if options.get("verbosity") > 1:
                    self.stdout.write(
                        f"Deleting duplicate SOA record '{record}' for zone '{zone}'"
                    )
                record.delete()

            zone.update_soa_record()

    def _zone_update_arpa_network(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Updating the ARPA network for reverse zones")

        for zone in Zone.objects.filter(name__endswith=".arpa"):
            if zone.arpa_network != (arpa_network := zone.network_from_name):
                if options.get("verbosity") > 1:
                    self.stdout.write(
                        f"Setting the ARPA network for zone '{zone}' to '{arpa_network}'"
                    )

                zone.arpa_network = arpa_network
                zone.save()

    def _record_cleanup_disable_ptr(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Updating 'Disable PTR' for non-address records")

        records = Record.objects.filter(
            disable_ptr=True,
        ).exclude(type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA))

        for record in records:
            if options.get("verbosity") > 1:
                self.stdout.write(
                    f"Setting 'Disable PTR' to False for record '{record}'"
                )

            record.disable_ptr = False
            record.save(update_fields=["disable_ptr"])

    def _record_update_ptr_records(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Updating the PTR record for all address records")

        for record in Record.objects.filter(
            type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA)
        ):
            record.save(update_fields=["ptr_record"])

    def _record_update_ip_address(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Updating the IP address for all address and PTR records")

        for record in Record.objects.filter(
            type__in=(
                RecordTypeChoices.A,
                RecordTypeChoices.AAAA,
                RecordTypeChoices.PTR,
            )
        ):
            if record.is_ptr_record:
                if record.ip_address != record.address_from_name:
                    if options.get("verbosity") > 1:
                        self.stdout.write(
                            f"Setting the IP Address for pointer record '{record}' to '{record.address_from_name}'"
                        )
                    record.ip_address = record.address_from_name
                    record.save()
            else:
                if record.ip_address != IPAddress(record.value):
                    if options.get("verbosity") > 1:
                        self.stdout.write(
                            f"Updating the IP address for address record '{record}' to '{IPAddress(record.value)}'"
                        )
                    record.ip_address = record.value
                    record.save()

    def _record_remove_orphaned_ptr_records(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Removing orphaned managed PTR records")

        orphaned_ptr_records = Record.objects.filter(
            type=RecordTypeChoices.PTR,
            managed=True,
            address_records__isnull=True,
        )

        for record in orphaned_ptr_records:
            if options.get("verbosity") > 1:
                self.stdout.write(f"Removing orphaned PTR record '{record}'")
            record.delete()

    def _record_remove_orphaned_address_records(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Removing orphaned managed address records")

        orphaned_address_records = Record.objects.filter(
            type__in=(RecordTypeChoices.A, RecordTypeChoices.AAAA),
            managed=True,
            ipam_ip_address__isnull=True,
        )

        for record in orphaned_address_records:
            if options.get("verbosity") > 1:
                self.stdout.write(f"Removing orphaned address record '{record}'")
            record.delete()

    def _record_remove_ptr_records_from_inactive_zones(self, **options):
        if options.get("verbosity"):
            self.stdout.write("Removing managed PTR records from inactive zones")

        for record in Record.objects.exclude(
            zone__status__in=ZONE_ACTIVE_STATUS_LIST,
        ).filter(
            type=RecordTypeChoices.PTR,
            managed=True,
        ):
            record.delete()
