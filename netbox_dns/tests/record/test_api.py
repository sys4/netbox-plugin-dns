from django.urls import reverse
from rest_framework import status
from unittest import skip

from netbox_dns.choices import RecordTypeChoices
from netbox_dns.models import NameServer, Record, View, Zone
from netbox_dns.tests.custom import (
    APITestCase,
    CustomFieldTargetAPIMixin,
    NetBoxDNSGraphQLMixin,
)
from utilities.testing import APIViewTestCases


class RecordAPITestCase(
    APITestCase,
    APIViewTestCases.GetObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.UpdateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
    NetBoxDNSGraphQLMixin,
    CustomFieldTargetAPIMixin,
    APIViewTestCases.GraphQLTestCase,
):
    model = Record
    brief_fields = [
        "active",
        "description",
        "display",
        "expired",
        "fqdn",
        "id",
        "managed",
        "name",
        "status",
        "ttl",
        "type",
        "url",
        "value",
        "zone",
    ]
    user_permissions = [
        "netbox_dns.view_zone",
    ]
    bulk_update_data = {
        "ttl": 19200,
    }

    @classmethod
    def setUpTestData(cls):
        zone_data = {
            **Zone.get_defaults(),
            "soa_mname": NameServer.objects.create(name="ns1.example.com"),
            "soa_rname": "hostmaster.example.com",
            "soa_serial_auto": False,
        }

        views = (
            View(name="view1"),
            View(name="view2"),
        )
        View.objects.bulk_create(views)

        default_view = View.get_default_view()
        cls.zones = (
            Zone(name="zone1.example.com", **zone_data, view=default_view),
            Zone(name="zone2.example.com", **zone_data, view=default_view),
            Zone(name="zone3.example.com", **zone_data, view=default_view),
            Zone(name="zone1.example.com", **zone_data, view=views[0]),
            Zone(name="zone2.example.com", **zone_data, view=views[0]),
            Zone(name="zone3.example.com", **zone_data, view=views[0]),
            Zone(name="zone1.example.com", **zone_data, view=views[1]),
            Zone(name="zone2.example.com", **zone_data, view=views[1]),
            Zone(name="zone3.example.com", **zone_data, view=views[1]),
        )
        Zone.objects.bulk_create(cls.zones)

        records = (
            Record(
                zone=cls.zones[0],
                type=RecordTypeChoices.A,
                name="example1",
                value="192.168.1.1",
                ttl=5000,
            ),
            Record(
                zone=cls.zones[1],
                type=RecordTypeChoices.AAAA,
                name="example2",
                value="fe80::dead:beef",
                ttl=6000,
            ),
            Record(
                zone=cls.zones[2],
                type=RecordTypeChoices.TXT,
                name="example3",
                value="TXT Record",
                ttl=7000,
            ),
            Record(
                zone=cls.zones[3],
                type=RecordTypeChoices.A,
                name="example1",
                value="192.168.1.1",
                ttl=5000,
                expiration_date="2026-06-30",
            ),
            Record(
                zone=cls.zones[4],
                type=RecordTypeChoices.AAAA,
                name="example2",
                value="fe80::dead:beef",
                ttl=6000,
                expiration_date="2026-05-21",
            ),
            Record(
                zone=cls.zones[5],
                type=RecordTypeChoices.TXT,
                name="example3",
                value="TXT Record",
                ttl=7000,
                expiration_date="2066-01-07",
            ),
            Record(
                zone=cls.zones[6],
                type=RecordTypeChoices.A,
                name="example1",
                value="192.168.1.1",
                ttl=5000,
            ),
            Record(
                zone=cls.zones[7],
                type=RecordTypeChoices.AAAA,
                name="example2",
                value="fe80::dead:beef",
                ttl=6000,
            ),
            Record(
                zone=cls.zones[8],
                type=RecordTypeChoices.TXT,
                name="example3",
                value="TXT Record",
                ttl=7000,
            ),
        )
        for record in records:
            record.save()

        cls.create_data = [
            {
                "zone": cls.zones[0].pk,
                "type": RecordTypeChoices.A,
                "name": "example4",
                "value": "1.1.1.1",
                "ttl": 9600,
            },
            {
                "zone": cls.zones[1].pk,
                "type": RecordTypeChoices.AAAA,
                "name": "example5",
                "value": "fe80::dead:beef",
                "disable_ptr": True,
                "ttl": 9600,
            },
            {
                "zone": cls.zones[2].pk,
                "type": RecordTypeChoices.TXT,
                "name": "example6",
                "value": "TXT Record",
                "ttl": 9600,
            },
            {
                "zone": cls.zones[3].pk,
                "type": RecordTypeChoices.A,
                "name": "example4",
                "value": "1.1.1.1",
                "ttl": 9600,
            },
            {
                "zone": cls.zones[4].pk,
                "type": RecordTypeChoices.AAAA,
                "name": "example5",
                "value": "fe80::dead:beef",
                "disable_ptr": True,
                "ttl": 9600,
            },
            {
                "zone": cls.zones[5].pk,
                "type": RecordTypeChoices.TXT,
                "name": "example6",
                "value": "TXT Record",
                "ttl": 9600,
            },
            {
                "zone": cls.zones[6].pk,
                "type": RecordTypeChoices.A,
                "name": "example4",
                "value": "1.1.1.1",
                "ttl": 9600,
            },
            {
                "zone": cls.zones[7].pk,
                "type": RecordTypeChoices.AAAA,
                "name": "example5",
                "value": "fe80::dead:beef",
                "disable_ptr": True,
                "ttl": 9600,
            },
            {
                "zone": cls.zones[8].pk,
                "type": RecordTypeChoices.TXT,
                "name": "example6",
                "value": "TXT Record",
                "ttl": 9600,
            },
        ]

    @skip("TBD: Fails with NetBox 4.7.0b1")
    def test_bulk_create_objects_invalid_item(self):
        pass

    def test_create_managed_record(self):
        self.add_permissions("netbox_dns.add_record")

        url = reverse("plugins-api:netbox_dns-api:record-list")
        data = {
            "name": "name42",
            "zone": self.zones[0].pk,
            "type": RecordTypeChoices.AAAA,
            "value": "fe80::dead:beef",
            "managed": True,
        }

        response = self.client.post(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_update_managed_record(self):
        record = Record.objects.create(
            name="name1",
            zone=self.zones[0],
            type=RecordTypeChoices.A,
            value="10.0.0.1",
            managed=True,
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.change_record")
        data = {
            "value": "10.0.0.2",
        }
        response = self.client.patch(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_update_records_managed(self):
        record = Record.objects.create(
            name="name1", zone=self.zones[0], type=RecordTypeChoices.A, value="10.0.0.1"
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.change_record")
        data = {
            "managed": True,
        }
        response = self.client.patch(url, data, format="json", **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_delete_managed_record(self):
        record = Record.objects.create(
            name="name1",
            zone=self.zones[0],
            type=RecordTypeChoices.A,
            value="10.0.0.1",
            managed=True,
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.delete_record")

        response = self.client.delete(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_record_expired(self):
        record = Record.objects.create(
            name="name1",
            zone=self.zones[0],
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
            expiration_date="2026-06-02",
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.view_record")

        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertTrue(response.json().get("expired"))

    def test_record_expired_future_false(self):
        record = Record.objects.create(
            name="name1",
            zone=self.zones[0],
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
            expiration_date="2226-06-30",
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.view_record")

        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertFalse(response.json().get("expired"))

    def test_record_expired_no_expiration_date_false(self):
        record = Record.objects.create(
            name="name1",
            zone=self.zones[0],
            type=RecordTypeChoices.AAAA,
            value="2001:db8::1",
        )

        url = reverse(
            "plugins-api:netbox_dns-api:record-detail", kwargs={"pk": record.pk}
        )
        self.add_permissions("netbox_dns.view_record")

        response = self.client.get(url, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertFalse(response.json().get("expired"))
