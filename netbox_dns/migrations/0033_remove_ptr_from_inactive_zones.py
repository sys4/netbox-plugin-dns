from django.db import migrations

from netbox.plugins.utils import get_plugin_config
from netbox_dns.choices import RecordTypeChoices

ZONE_ACTIVE_STATUS_LIST = get_plugin_config("netbox_dns", "zone_active_status")


def remove_ptr_from_inactive_zones(apps, schema_editor):
    Record = apps.get_model("netbox_dns", "Record")

    inactive_ptr_records = Record.objects.exclude(
        zone__status__in=ZONE_ACTIVE_STATUS_LIST,
    ).filter(
        type=RecordTypeChoices.PTR,
        managed=True,
    )

    for record in inactive_ptr_records:
        record.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_dns", "0032_record_expiration_date"),
    ]

    operations = [
        migrations.RunPython(remove_ptr_from_inactive_zones),
    ]
