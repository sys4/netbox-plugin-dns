from dns import name as dns_name

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from netbox_dns.models import Zone, Record
from netbox_dns.choices import RecordStatusChoices


class Command(BaseCommand):
    help = "Check DNS records for zone cut conflicts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            default=False,
            help="Fix records masked by zone cut conflicts (experimental!)",
        )

    def handle(self, *model_names, **options):
        if options.get("verbosity"):
            self.stdout.write("Checking all records for zone cut conflicts")

        for zone in Zone.objects.all():
            if not zone.descendant_zones.exists():
                continue

            for record in zone.records.filter(active=True, managed=False):
                try:
                    record.check_zone_cut_conflict()
                except ValidationError:
                    self.stdout.write(
                        f"WARNING: Record {record} in zone {zone} is masked by a descendant zone"
                    )

                    if options.get("fix"):
                        new_zone = record.zone.descendant_zones.filter(
                            name__endswith=record.fqdn.rstrip(".")
                        ).last()
                        new_name = (
                            dns_name.from_text(record.fqdn)
                            .relativize(dns_name.from_text(new_zone.name))
                            .to_text()
                        )

                        if Record.objects.filter(
                            zone=new_zone,
                            name=new_name,
                            value=record.value,
                            type=record.type,
                        ).exists():
                            self.stdout.write(
                                f"Record {record} is already present in zone {new_zone}, disabling it"
                            )
                            record.status = RecordStatusChoices.STATUS_INACTIVE
                        else:
                            self.stdout.write(
                                f"Moving record {record} to zone {new_zone}"
                            )
                            record.name = new_name
                            record.zone = new_zone

                        try:
                            record.save()
                        except ValidationError as exc:
                            self.stdout.write(f"ERROR: {exc.messages[0]}")

        if options.get("verbosity"):
            self.stdout.write("Checking complete")
