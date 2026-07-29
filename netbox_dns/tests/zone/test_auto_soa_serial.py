from datetime import datetime, timedelta
from math import ceil
from time import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from dns import rdata

from netbox_dns.choices import (
    RecordClassChoices,
    RecordTypeChoices,
    ZoneEPPStatusChoices,
    ZoneStatusChoices,
)
from netbox_dns.models import (
    DNSSECPolicy,
    NameServer,
    Record,
    Registrar,
    RegistrationContact,
    Zone,
)
from tenancy.models import Tenant


def set_soa_serial_back(zone):
    zone.last_updated = datetime.now() - timedelta(days=1)
    zone.soa_serial = ceil(zone.last_updated.timestamp())
    super(Zone, zone).save()
    zone.update_soa_record()


def parse_soa_value(soa):
    return rdata.from_text(
        rdclass=RecordClassChoices.IN, rdtype=RecordTypeChoices.SOA, tok=soa
    )


class ZoneAutoSOASerialTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.defaults = settings.PLUGINS_CONFIG.get("netbox_dns")

        cls.start_time = int(time())

        cls.nameservers = (
            NameServer.objects.create(name="ns1.example.com"),
            NameServer.objects.create(name="ns2.example.com"),
        )

        cls.zone_data = {
            "soa_mname": cls.nameservers[0],
            "soa_rname": "hostmaster.example.com",
        }

        cls.zones = (
            Zone(
                name="zone1.example.com",
                **cls.zone_data,
                soa_serial_auto=True,
            ),
            Zone(
                name="zone2.example.com",
                **cls.zone_data,
                soa_serial_auto=False,
            ),
            Zone(
                name="1.0.10.in-addr.arpa",
                **cls.zone_data,
                soa_serial_auto=True,
            ),
            Zone(
                name="2.0.10.in-addr.arpa",
                **cls.zone_data,
                soa_serial_auto=False,
            ),
        )
        for zone in cls.zones:
            zone.save()

        # +
        # Reset the SOA serial to 1 for soa_serial_auto zones
        # -
        for zone in (cls.zones[0], cls.zones[2]):
            zone.soa_serial = 1628586244
            super(Zone, zone).save()

    def test_soa_serial_fixed(self):
        zone = self.zones[1]

        self.assertEqual(zone.soa_serial, 1)

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                **settings.PLUGINS_CONFIG["netbox_dns"],
                "zone_soa_serial_format": "date-counter",
            }
        }
    )
    def test_date_counter_soa_serial(self):
        zone = self.zones[0]
        today = int(datetime.now().strftime("%Y%m%d00"))
        zone.soa_serial = None

        self.assertEqual(zone.format_auto_serial(datetime.now().timestamp()), today)

        zone.soa_serial = today
        self.assertEqual(zone.format_auto_serial(datetime.now().timestamp()), today + 1)

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                **settings.PLUGINS_CONFIG["netbox_dns"],
                "zone_soa_serial_format": "date-counter",
            }
        }
    )
    def test_date_counter_soa_serial_new_day(self):
        zone = self.zones[0]
        zone.soa_serial = 2020010199

        self.assertEqual(
            zone.format_auto_serial(datetime.now().timestamp()),
            int(datetime.now().strftime("%Y%m%d00")),
        )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                **settings.PLUGINS_CONFIG["netbox_dns"],
                "zone_soa_serial_format": "date-counter",
            }
        }
    )
    def test_date_counter_soa_serial_daily_limit(self):
        zone = self.zones[0]
        zone.soa_serial = int(datetime.now().strftime("%Y%m%d99"))

        with self.assertRaises(ValidationError):
            zone.format_auto_serial(datetime.now().timestamp())

    def test_increase_soa_serial(self):
        zone = self.zones[1]

        zone.soa_serial = 2100000000
        zone.save()

        self.assertEqual(zone.soa_serial, 2100000000)

    def test_decrease_soa_serial(self):
        zone = self.zones[1]
        zone.soa_serial = 2100000000
        zone.save()

        zone.soa_serial = 42
        with self.assertRaises(ValidationError):
            zone.save()

    def test_increase_soa_serial_excessive_increment(self):
        zone = self.zones[1]

        zone.soa_serial = 4200000000
        with self.assertRaises(ValidationError):
            zone.save()

    def test_increase_soa_serial_wrap(self):
        zone = self.zones[1]

        zone.soa_serial = 2100000000
        zone.save()

        zone.soa_serial = 4200000000
        zone.save()

        zone.soa_serial = 42
        zone.save()

        self.assertEqual(zone.soa_serial, 42)

    def test_increase_soa_serial_wrap_excessive_increment(self):
        zone = self.zones[1]

        zone.soa_serial = 2100000000
        zone.save()

        zone.soa_serial = 4200000000
        zone.save()

        zone.soa_serial = 2100000000
        with self.assertRaises(ValidationError):
            zone.save()

    def test_change_to_soa_serial_auto_low_serial(self):
        zone = self.zones[1]

        zone.soa_serial_auto = True
        zone.save()

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

    def test_change_to_soa_serial_auto_high_serial(self):
        zone = self.zones[1]
        zone.soa_serial = 2100000000
        zone.save()

        zone.soa_serial_auto = True
        with self.assertRaises(ValidationError):
            zone.save()

    def test_change_to_soa_serial_fixed_low_serial(self):
        zone = self.zones[0]

        zone.soa_serial_auto = False
        zone.soa_serial = 42

        with self.assertRaises(ValidationError):
            zone.save()

    def test_change_to_soa_serial_fixed_high_serial(self):
        zone = self.zones[0]

        zone.soa_serial_auto = False
        zone.soa_serial = 2100000000

        zone.save()

        self.assertEqual(zone.soa_serial, 2100000000)

    def modify_zone_soa_serial_auto(self):
        zone = self.zones[0]

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        zone.soa_rname = "admin.example.com"
        zone.save()

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

    @override_settings(PLUGINS_CONFIG={"netbox_dns": {"zone_soa_serial": 2100000000}})
    def test_missing_soa_serial(self):
        zone = self.zones[0]
        zone.soa_serial = None
        zone.soa_serial_auto = False

        zone.save()

        self.assertEqual(zone.soa_serial, 2100000000)

    @override_settings(PLUGINS_CONFIG={"netbox_dns": {}})
    def test_missing_soa_serial_no_default(self):
        zone = self.zones[0]
        zone.soa_serial = None
        zone.soa_serial_auto = False

        with self.assertRaises(ValidationError):
            zone.save()

    def test_add_nameservers_soa_serial_auto(self):
        zone = self.zones[0]

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        zone.nameservers.add(self.nameservers[0])
        zone.nameservers.add(self.nameservers[1])

        self.assertTrue(int(zone.soa_serial) < self.start_time)

    def test_remove_nameservers_soa_serial_auto(self):
        zone = self.zones[0]

        zone.nameservers.add(self.nameservers[0])
        zone.nameservers.add(self.nameservers[1])

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        for nameserver in zone.nameservers.all():
            zone.nameservers.remove(nameserver)

        zone.refresh_from_db()

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

    def test_create_record_soa_serial_auto(self):
        zone = self.zones[0]

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        Record.objects.create(
            zone=zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        zone.refresh_from_db()

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

    def test_update_record_soa_serial_auto(self):
        zone = self.zones[0]

        record = Record.objects.create(
            zone=zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        record.ttl = 424242
        record.save()

        self.assertTrue(int(zone.soa_serial) >= self.start_time)

    def test_update_soa_record_soa_serial_auto(self):
        zone = self.zones[0]

        set_soa_serial_back(zone)

        self.assertTrue(int(zone.soa_serial) < self.start_time)

        soa_record = Record.objects.get(zone=zone, type=RecordTypeChoices.SOA)
        soa_record.ttl = 424242
        soa_record.save()

        zone.refresh_from_db()

        self.assertFalse(int(zone.soa_serial) >= self.start_time)

    def test_create_ptr_soa_serial_fixed(self):
        f_zone = self.zones[0]
        r_zone = self.zones[3]

        f_record = Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.2.42",
            ttl=86400,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            value=f"{f_record.name}.{f_zone.name}.",
            zone=r_zone,
        )
        r_zone = Zone.objects.get(pk=r_record.zone.pk)

        self.assertEqual(r_zone.soa_serial, 1)

    def test_create_address_with_ptr_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)

        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)

    def test_delete_address_with_ptr_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        f_record = Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        f_record.delete()

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)

        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)

    def test_disable_ptr_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        f_record = Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        f_record.disable_ptr = True
        f_record.save()

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)

        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)

    def test_enable_ptr_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        f_record = Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
            disable_ptr=True,
        )

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()

        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)

        f_record.disable_ptr = False
        f_record.save()

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)

        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)

    def test_rfc2317_create_address_parent_managed_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        rfc2317_zone = Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            **self.zone_data,
            soa_serial_auto=True,
            rfc2317_prefix="10.0.1.0/26",
            rfc2317_parent_managed=True,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)
        set_soa_serial_back(rfc2317_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()
        rfc2317_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)
        rfc2317_soa_record = Record.objects.get(
            type=RecordTypeChoices.SOA, zone=rfc2317_zone
        )

        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)
        self.assertEqual(
            parse_soa_value(rfc2317_soa_record.value).serial, rfc2317_zone.soa_serial
        )

    def test_rfc2317_create_address_parent_unmanaged_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        rfc2317_zone = Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            **self.zone_data,
            soa_serial_auto=True,
            rfc2317_prefix="10.0.1.0/26",
            rfc2317_parent_managed=False,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)
        set_soa_serial_back(rfc2317_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()
        rfc2317_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)
        rfc2317_soa_record = Record.objects.get(
            type=RecordTypeChoices.SOA, zone=rfc2317_zone
        )

        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)
        self.assertEqual(
            parse_soa_value(rfc2317_soa_record.value).serial, rfc2317_zone.soa_serial
        )

    def test_rfc2317_set_parent_managed_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        rfc2317_zone = Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            **self.zone_data,
            soa_serial_auto=True,
            rfc2317_prefix="10.0.1.0/26",
            rfc2317_parent_managed=False,
        )

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)
        set_soa_serial_back(rfc2317_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        rfc2317_zone.rfc2317_parent_managed = True
        rfc2317_zone.save()

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()
        rfc2317_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)
        rfc2317_soa_record = Record.objects.get(
            type=RecordTypeChoices.SOA, zone=rfc2317_zone
        )

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)
        self.assertEqual(
            parse_soa_value(rfc2317_soa_record.value).serial, rfc2317_zone.soa_serial
        )

    def test_rfc2317_set_parent_unmanaged_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        rfc2317_zone = Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            **self.zone_data,
            soa_serial_auto=True,
            rfc2317_prefix="10.0.1.0/26",
            rfc2317_parent_managed=True,
        )

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)
        set_soa_serial_back(rfc2317_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        rfc2317_zone.rfc2317_parent_managed = False
        rfc2317_zone.save()

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()
        rfc2317_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)
        rfc2317_soa_record = Record.objects.get(
            type=RecordTypeChoices.SOA, zone=rfc2317_zone
        )

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) >= self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)
        self.assertEqual(
            parse_soa_value(rfc2317_soa_record.value).serial, rfc2317_zone.soa_serial
        )

    def test_rfc2317_create_address_parent_managed_disable_ptr_soa_serial_auto(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        rfc2317_zone = Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            **self.zone_data,
            soa_serial_auto=True,
            rfc2317_prefix="10.0.1.0/26",
            rfc2317_parent_managed=False,
        )

        set_soa_serial_back(f_zone)
        set_soa_serial_back(r_zone)
        set_soa_serial_back(rfc2317_zone)

        self.assertTrue(int(f_zone.soa_serial) < self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        Record.objects.create(
            zone=f_zone,
            name="name1",
            type=RecordTypeChoices.A,
            value="10.0.1.42",
            ttl=86400,
            disable_ptr=True,
        )

        f_zone.refresh_from_db()
        r_zone.refresh_from_db()
        rfc2317_zone.refresh_from_db()

        f_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=f_zone)
        r_soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=r_zone)
        rfc2317_soa_record = Record.objects.get(
            type=RecordTypeChoices.SOA, zone=rfc2317_zone
        )

        self.assertTrue(int(f_zone.soa_serial) >= self.start_time)
        self.assertTrue(int(r_zone.soa_serial) < self.start_time)
        self.assertTrue(int(rfc2317_zone.soa_serial) < self.start_time)

        self.assertEqual(parse_soa_value(f_soa_record.value).serial, f_zone.soa_serial)
        self.assertEqual(parse_soa_value(r_soa_record.value).serial, r_zone.soa_serial)
        self.assertEqual(
            parse_soa_value(rfc2317_soa_record.value).serial, rfc2317_zone.soa_serial
        )

    def test_update_description_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.description = "Changed"
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_status_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.status = ZoneStatusChoices.STATUS_DYNAMIC
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_dnssec_policy_no_soa_change(self):
        zone = self.zones[0]
        dnssec_policy = DNSSECPolicy.objects.create(name="Test Policy")

        old_soa_serial = zone.soa_serial

        zone.dnssec_policy = dnssec_policy
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_registrar_no_soa_change(self):
        zone = self.zones[0]
        registrar = Registrar.objects.create(name="Test Registrar")

        old_soa_serial = zone.soa_serial

        zone.registrar = registrar
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_registry_domain_id_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.registry_domain_id = 42
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_expiration_date_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.expiration_date = "2042-04-01"
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_domain_status_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.domain_status = ZoneEPPStatusChoices.EPP_STATUS_OK
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_registrant_no_soa_change(self):
        zone = self.zones[0]
        contact = RegistrationContact.objects.create(contact_id="Test Contact")

        old_soa_serial = zone.soa_serial

        zone.registrant = contact
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_admin_c_no_soa_change(self):
        zone = self.zones[0]
        contact = RegistrationContact.objects.create(contact_id="Test Contact")

        old_soa_serial = zone.soa_serial

        zone.admin_c = contact
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_tech_c_no_soa_change(self):
        zone = self.zones[0]
        contact = RegistrationContact.objects.create(contact_id="Test Contact")

        old_soa_serial = zone.soa_serial

        zone.tech_c = contact
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_billing_c_no_soa_change(self):
        zone = self.zones[0]
        contact = RegistrationContact.objects.create(contact_id="Test Contact")

        old_soa_serial = zone.soa_serial

        zone.billing_c = contact
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_rfc2317_parent_managed_no_soa_change(self):
        zone = self.zones[0]

        old_soa_serial = zone.soa_serial

        zone.rfc2317_parent_managed = False
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)

    def test_update_tenant_no_soa_change(self):
        zone = self.zones[0]
        tenant = Tenant.objects.create(name="Test Tenant")

        old_soa_serial = zone.soa_serial

        zone.tenant = tenant
        zone.save()
        zone.refresh_from_db()

        self.assertEqual(zone.soa_serial, old_soa_serial)
