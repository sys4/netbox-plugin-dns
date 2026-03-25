from django.test import TestCase

from netbox_dns.models import NameServer, Zone, Record
from netbox_dns.choices import RecordTypeChoices


class RecordDefaultTTLTestSet(TestCase):
    @classmethod
    def setUpTestData(cls):
        zone = Zone.objects.create(
            name="zone1.example.com",
            soa_mname=NameServer.objects.create(name="ns1.example.com"),
            soa_rname="hostmaster.example.com",
        )

        cls.record_data = {
            "name": "name1",
            "zone": zone,
            "type": RecordTypeChoices.AAAA,
            "value": "2001:db8::dead:beef",
        }

        cls.test_settings = {
            "PLUGINS_CONFIG": {
                "netbox_dns": {
                    "record_type_default_ttl": {
                        RecordTypeChoices.AAAA: 42,
                    }
                }
            }
        }

    def test_no_default_ttl(self):
        record = Record.objects.create(
            **self.record_data,
            ttl=None,
        )

        self.assertEqual(record.ttl, None)

    def test_default_ttl(self):
        with self.settings(**self.test_settings):
            record = Record.objects.create(
                **self.record_data,
                ttl=None,
            )

        self.assertEqual(record.ttl, 42)

    def test_default_ttl_override(self):
        with self.settings(**self.test_settings):
            record = Record.objects.create(
                **self.record_data,
                ttl=23,
            )

        self.assertEqual(record.ttl, 23)
