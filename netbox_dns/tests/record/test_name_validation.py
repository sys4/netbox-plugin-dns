from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError

from netbox_dns.models import NameServer, Zone, Record
from netbox_dns.choices import RecordTypeChoices


class RecordNameValidationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        zone_data = {
            "soa_mname": NameServer.objects.create(name="ns1.example.com"),
            "soa_rname": "hostmaster.example.com",
        }

        cls.record_data = {
            "type": RecordTypeChoices.AAAA,
            "value": "fe80:dead:beef::",
        }

        cls.zones = (
            Zone(name="zone1.example.com", **zone_data),
            Zone(name="zone2.example.com.", **zone_data),
            Zone(name="zone240" + 22 * ".123456789" + ".example.com", **zone_data),
            Zone(name="zone240" + 22 * ".987654321" + ".example.com.", **zone_data),
            Zone(name="f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **zone_data),
            Zone(name="example.com", **zone_data),
        )
        for zone in cls.zones:
            zone.save()

    def test_name_validation_ok(self):
        records = (
            {"name": "*", "zone": self.zones[0]},
            {"name": "name1", "zone": self.zones[0]},
            {"name": "@", "zone": self.zones[0]},
            {"name": "*", "zone": self.zones[1]},
            {"name": "*.sub", "zone": self.zones[0]},
            {"name": "*.sub.zone1.example.com", "zone": self.zones[0]},
            {"name": "*.sub.zone2.example.com.", "zone": self.zones[1]},
            {"name": "name2.zone1.example.com.", "zone": self.zones[0]},
            {"name": "name1", "zone": self.zones[1]},
            {"name": "@", "zone": self.zones[2]},
            {"name": "*", "zone": self.zones[2]},
            {"name": "name2.zone2.example.com.", "zone": self.zones[1]},
            {"name": "name-1", "zone": self.zones[0]},
            {"name": "name-2.zone1.example.com.", "zone": self.zones[0]},
            {"name": "name-1", "zone": self.zones[1]},
            {"name": "name-2.zone2.example.com.", "zone": self.zones[1]},
            {"name": "x" * 13, "zone": self.zones[2]},
            {"name": "x" * 13, "zone": self.zones[3]},
            {"name": "x" * 63 + f".{self.zones[0].name}.", "zone": self.zones[0]},
            {"name": "x" * 63 + f".{self.zones[1].name}", "zone": self.zones[1]},
            {"name": "xn--nme1-loa", "zone": self.zones[0]},
            {"name": "xn--nme2-loa.zone1.example.com.", "zone": self.zones[0]},
            {"name": "XN--nme3-loa", "zone": self.zones[0]},
            {"name": "XN--nme4-loa.zone1.example.com.", "zone": self.zones[0]},
        )

        for record in records:
            Record.objects.create(
                name=record.get("name"), zone=record.get("zone"), **self.record_data
            )

    def test_tlsa_validation_ok(self):
        record = Record.objects.create(
            name="_25._tcp.mx1",
            zone=self.zones[0],
            type=RecordTypeChoices.TLSA,
            value="3 1 1 4048c63a12234d9edf4d28113929cab21f8307a6c26732c2f5d103a322b612e1",
        )
        self.assertEqual(record.name, "_25._tcp.mx1")

    def test_srv_validation_ok(self):
        record = Record.objects.create(
            name="_ldaps._tcp",
            zone=self.zones[0],
            type=RecordTypeChoices.SRV,
            value="10 5 636 server.example.com.",
        )
        self.assertEqual(record.name, "_ldaps._tcp")

    def test_txt_validation_ok(self):
        record = Record.objects.create(
            name="_dmarc",
            zone=self.zones[0],
            type=RecordTypeChoices.TXT,
            value="v=DMARC1;p=reject",
        )
        self.assertEqual(record.name, "_dmarc")

    def test_name_validation_failure(self):
        records = (
            {"name": "_name1", "zone": self.zones[0]},
            {"name": "name1..", "zone": self.zones[0]},
            {"name": "@.", "zone": self.zones[0]},
            {"name": "*.", "zone": self.zones[0]},
            {"name": "*.sub.", "zone": self.zones[0]},
            {"name": "*.*", "zone": self.zones[0]},
            {"name": "*.*.", "zone": self.zones[0]},
            {"name": "name1.zone2.example.com.", "zone": self.zones[0]},
            {"name": "name1.zone1.example.com.", "zone": self.zones[1]},
            {"name": "name_1", "zone": self.zones[0]},
            {"name": "name_1.zone1.example.com.", "zone": self.zones[0]},
            {"name": "-name1", "zone": self.zones[0]},
            {"name": "-name1.zone1.example.com.", "zone": self.zones[0]},
            {"name": "name1-", "zone": self.zones[0]},
            {"name": "name1-.zone1.example.com.", "zone": self.zones[0]},
            {"name": "na--me1", "zone": self.zones[0]},
            {"name": "na--me1.zone1.example.com.", "zone": self.zones[0]},
            {"name": "x" * 14, "zone": self.zones[2]},
            {"name": "x" * 14, "zone": self.zones[3]},
            {"name": "\\000" * 14, "zone": self.zones[2]},
            {"name": "\\000" * 14, "zone": self.zones[3]},
            {"name": "x" * 64 + f".{self.zones[0].name}.", "zone": self.zones[0]},
            {"name": "x" * 64 + f".{self.zones[1].name}", "zone": self.zones[1]},
            {"name": "xn--n", "zone": self.zones[0]},
            {"name": "xn--n.zone1.example.com.", "zone": self.zones[0]},
            {"name": "na/me1.zone1.example.com.", "zone": self.zones[0]},
        )

        for record in records:
            with self.assertRaises(ValidationError):
                Record.objects.create(
                    name=record.get("name"), zone=record.get("zone"), **self.record_data
                )

    def test_name_no_lowercase(self):
        record = Record.objects.create(
            name="NAME1", zone=self.zones[0], **self.record_data
        )

        self.assertEqual(record.fqdn, "NAME1.zone1.example.com.")

    @override_settings(
        PLUGINS_CONFIG={"netbox_dns": {"convert_names_to_lowercase": True}}
    )
    def test_name_lowercase(self):
        record = Record.objects.create(
            name="NAME1", zone=self.zones[0], **self.record_data
        )

        self.assertEqual(record.fqdn, "name1.zone1.example.com.")

    def test_name_case_insensitive_conflict(self):
        Record.objects.create(name="name1", zone=self.zones[0], **self.record_data)

        with self.assertRaises(ValidationError):
            Record.objects.create(name="NAME1", zone=self.zones[0], **self.record_data)

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_underscores_in_labels": True,
                "tolerate_leading_underscore_types": ["TXT", "SRV"],
                "tolerate_non_rfc1035_types": [],
            }
        }
    )
    def test_name_validation_tolerant_ok(self):
        records = (
            {"name": "name_1", "zone": self.zones[0]},
            {"name": "name_1.zone1.example.com.", "zone": self.zones[0]},
        )

        for record in records:
            Record.objects.create(
                name=record.get("name"), zone=record.get("zone"), **self.record_data
            )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_underscores_in_labels": True,
                "tolerate_leading_underscore_types": ["TXT", "SRV"],
                "tolerate_non_rfc1035_types": [],
            }
        }
    )
    def test_srv_validation_tolerant_ok(self):
        record = Record.objects.create(
            name="_ldaps._tcp",
            zone=self.zones[0],
            type=RecordTypeChoices.SRV,
            value="10 5 636 server.example.com.",
        )
        self.assertEqual(record.name, "_ldaps._tcp")

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_underscores_in_labels": True,
                "tolerate_leading_underscore_types": ["TXT", "SRV"],
                "tolerate_non_rfc1035_types": [],
            }
        }
    )
    def test_txt_validation_tolerant_ok(self):
        records = (
            {
                "name": "_dmarc",
                "zone": self.zones[0],
                "type": RecordTypeChoices.TXT,
                "value": "v=DMARC1;p=reject",
            },
            {
                "name": "key1_op16._domainkey",
                "zone": self.zones[0],
                "type": RecordTypeChoices.TXT,
                "value": "test",
            },
        )
        for record in records:
            record_object = Record.objects.create(**record)
            self.assertEqual(record_object.name, record.get("name"))

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_underscores_in_labels": True,
                "tolerate_leading_underscore_types": ["TXT", "SRV"],
                "tolerate_non_rfc1035_types": [],
            }
        }
    )
    def test_name_validation_tolerant_failure(self):
        records = (
            {"name": "_name1", "zone": self.zones[0]},
            {"name": "_name1.zone1.example.com.", "zone": self.zones[0]},
            {"name": "name1_", "zone": self.zones[0]},
            {"name": "name1_.zone1.example.com.", "zone": self.zones[0]},
        )

        for record in records:
            with self.assertRaises(ValidationError):
                Record.objects.create(
                    name=record.get("name"), zone=record.get("zone"), **self.record_data
                )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_characters_in_zone_labels": "/",
            }
        }
    )
    def test_name_validation_allow_special_character_ok(self):
        zone = self.zones[0]
        zone.name = "zo/ne1.example.com"
        zone.save()

        record = Record.objects.create(name="name1", zone=zone, **self.record_data)

        self.assertEqual(record.fqdn, "name1.zo/ne1.example.com.")

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "tolerate_characters_in_zone_labels": "/",
            }
        }
    )
    def test_name_validation_allow_special_character_failure(self):
        with self.assertRaises(ValidationError):
            Record.objects.create(name="na/me1", zone=self.zones[0], **self.record_data)

    def test_zone_cut_conflict_failure(self):
        zone = self.zones[5]

        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="zone1",
                zone=zone,
                type=RecordTypeChoices.TXT,
                value="test",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="zone1",
                zone=zone,
                type=RecordTypeChoices.A,
                value="192.0.2.1",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="zone1",
                zone=zone,
                type=RecordTypeChoices.AAAA,
                value="2001:db8::1",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="name1.zone1",
                zone=zone,
                type=RecordTypeChoices.NS,
                value="ns1.zone1.example.com",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="name2.zone1",
                zone=zone,
                type=RecordTypeChoices.DS,
                value="55286 8 2 87E39BB0ACB924446AB5E2C7C4BF853FBF05FDA42DB74262D04C439E 8A724E7E",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="name1.zone1",
                zone=zone,
                type=RecordTypeChoices.TXT,
                value="test",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="name1.zone1",
                zone=zone,
                type=RecordTypeChoices.A,
                value="192.0.2.1",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="name1.zone1",
                zone=zone,
                type=RecordTypeChoices.AAAA,
                value="2001:db8::1",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="ns1.zone1",
                zone=zone,
                type=RecordTypeChoices.A,
                value="192.0.2.1",
            )
        with self.assertRaises(ValidationError):
            Record.objects.create(
                name="ns2.zone1",
                zone=zone,
                type=RecordTypeChoices.AAAA,
                value="2001:db8::1",
            )

    def test_zone_cut_delegation_ok(self):
        zone = self.zones[5]
        child_zone = self.zones[0]

        child_zone.nameservers.set(
            (
                NameServer.objects.create(name="ns1.zone1.example.com"),
                NameServer.objects.create(name="ns2.zone1.example.com"),
            )
        )

        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.NS,
            value="ns1.zone1.example.com",
        )
        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.DS,
            value="55286 8 2 87E39BB0ACB924446AB5E2C7C4BF853FBF05FDA42DB74262D04C439E 8A724E7E",
        )
        Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="192.0.2.1",
        )
        Record.objects.create(
            name="ns2.zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
        )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_zone_cut_conflict_nocheck_ok(self):
        zone = self.zones[5]

        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.TXT,
            value="test",
        )
        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="192.0.2.1",
        )
        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
        )
        Record.objects.create(
            name="name1.zone1",
            zone=zone,
            type=RecordTypeChoices.NS,
            value="ns1.zone1.example.com",
        )
        Record.objects.create(
            name="name2.zone1",
            zone=zone,
            type=RecordTypeChoices.DS,
            value="55286 8 2 87E39BB0ACB924446AB5E2C7C4BF853FBF05FDA42DB74262D04C439E 8A724E7E",
        )
        Record.objects.create(
            name="name1.zone1",
            zone=zone,
            type=RecordTypeChoices.TXT,
            value="test",
        )
        Record.objects.create(
            name="name1.zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="192.0.2.1",
        )
        Record.objects.create(
            name="name1.zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
        )
        Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="192.0.2.1",
        )
        Record.objects.create(
            name="ns2.zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
        )
