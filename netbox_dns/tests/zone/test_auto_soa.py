from dns import rdata

from django.test import TestCase

from netbox_dns.models import NameServer, Record, Zone
from netbox_dns.choices import (
    RecordClassChoices,
    RecordTypeChoices,
)


def parse_soa_value(soa):
    return rdata.from_text(
        rdclass=RecordClassChoices.IN, rdtype=RecordTypeChoices.SOA, tok=soa
    )


class ZoneAutoSOATestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nameservers = [
            NameServer(name="ns1.example.com"),
            NameServer(name="ns2.example.com"),
            NameServer(name="ns3.example.com."),
        ]
        NameServer.objects.bulk_create(cls.nameservers)

        cls.zone = Zone.objects.create(
            name="zone1.example.com",
            soa_mname=cls.nameservers[0],
            soa_rname="hostmaster.example.com",
        )

    def test_zone_soa(self):
        zone = self.zone

        soa_records = Record.objects.filter(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_records[0].value)

        self.assertTrue(
            all(
                (
                    zone.soa_mname.name + "." == soa.mname.to_text(),
                    zone.soa_rname + "." == soa.rname.to_text(),
                    zone.soa_serial == soa.serial,
                    zone.soa_refresh == soa.refresh,
                    zone.soa_retry == soa.retry,
                    zone.soa_expire == soa.expire,
                    zone.soa_minimum == soa.minimum,
                    zone.soa_ttl == soa_records[0].ttl,
                    len(soa_records) == 1,
                )
            )
        )

    def test_zone_soa_change_mname_no_dot(self):
        zone = self.zone
        nameserver2 = self.nameservers[1]

        zone.soa_mname = nameserver2
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(nameserver2.name + ".", soa.mname.to_text())

    def test_zone_soa_change_mname_dot(self):
        zone = self.zone
        nameserver3 = self.nameservers[2]

        zone.soa_mname = nameserver3
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(nameserver3.name, soa.mname.to_text())

    def test_zone_soa_change_rname_no_dot(self):
        zone = self.zone
        rname = "new-hostmaster.example.com"

        zone.soa_rname = rname
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(rname + ".", soa.rname.to_text())

    def test_zone_soa_change_rname_dot(self):
        zone = self.zone
        rname = "new-hostmaster.example.com."

        zone.soa_rname = rname
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(rname, soa.rname.to_text())

    def test_zone_soa_change_serial(self):
        zone = self.zone
        serial = 2100000000

        zone.soa_serial_auto = False
        zone.soa_serial = serial
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(serial, soa.serial)

    def test_zone_soa_change_refresh(self):
        zone = self.zone
        refresh = 23

        zone.soa_refresh = refresh
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(refresh, soa.refresh)

    def test_zone_soa_change_retry(self):
        zone = self.zone
        retry = 2342

        zone.soa_retry = retry
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(retry, soa.retry)

    def test_zone_soa_change_expire(self):
        zone = self.zone
        expire = 4223

        zone.soa_expire = expire
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(expire, soa.expire)

    def test_zone_soa_change_minimum(self):
        zone = self.zone
        minimum = 4223

        zone.soa_minimum = minimum
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)
        soa = parse_soa_value(soa_record.value)

        self.assertEqual(minimum, soa.minimum)

    def test_zone_soa_change_ttl(self):
        zone = self.zone
        ttl = 422342

        zone.soa_ttl = ttl
        zone.save()

        soa_record = Record.objects.get(type=RecordTypeChoices.SOA, zone=zone)

        self.assertEqual(ttl, soa_record.ttl)
