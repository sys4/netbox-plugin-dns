from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import Zone, NameServer, Record
from netbox_dns.choices import ZoneStatusChoices, RecordTypeChoices, RecordStatusChoices
from netbox_dns.filtersets import RecordFilterSet


class RecordFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = Record.objects.all()
    filterset = RecordFilterSet

    @classmethod
    def setUpTestData(cls):
        cls.tenant_groups = (
            TenantGroup(name="Tenant group 1", slug="tenant-group-1"),
            TenantGroup(name="Tenant group 2", slug="tenant-group-2"),
            TenantGroup(name="Tenant group 3", slug="tenant-group-3"),
        )
        for tenant_group in cls.tenant_groups:
            tenant_group.save()

        cls.tenants = (
            Tenant(name="Tenant 1", slug="tenant-1", group=cls.tenant_groups[0]),
            Tenant(name="Tenant 2", slug="tenant-2", group=cls.tenant_groups[1]),
            Tenant(name="Tenant 3", slug="tenant-3", group=cls.tenant_groups[2]),
        )
        Tenant.objects.bulk_create(cls.tenants)

        cls.zone_data = {
            "soa_rname": "hostmaster.example.com",
            "soa_mname": NameServer.objects.create(name="hostmaster.example.com"),
        }

        cls.zones = (
            Zone(name="zone1.example.com", **cls.zone_data),
            Zone(
                name="zone2.example.com",
                **cls.zone_data,
                status=ZoneStatusChoices.STATUS_DEPRECATED,
            ),
        )
        for zone in cls.zones:
            zone.save()

        cls.records = (
            Record(
                name="name1",
                description="Test Record 1",
                zone=cls.zones[0],
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[0],
            ),
            Record(
                name="name2",
                description="Test Record 2",
                zone=cls.zones[0],
                type=RecordTypeChoices.A,
                value="10.0.0.42",
                tenant=cls.tenants[0],
            ),
            Record(
                name="name3",
                description="Test Record 3",
                zone=cls.zones[0],
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[1],
                managed=True,
            ),
            Record(
                name="name5",
                description="Test Record 4",
                zone=cls.zones[0],
                type=RecordTypeChoices.TXT,
                value="Nothing to see here",
                status=RecordStatusChoices.STATUS_INACTIVE,
            ),
            Record(
                name="name1",
                description="Test Record 5",
                zone=cls.zones[1],
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[0],
            ),
            Record(
                name="name2",
                description="Test Record 6",
                zone=cls.zones[1],
                type=RecordTypeChoices.A,
                value="10.0.0.42",
                tenant=cls.tenants[0],
            ),
            Record(
                name="name3",
                description="Test Record 7",
                zone=cls.zones[1],
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[1],
                managed=True,
            ),
        )
        for record in cls.records:
            record.save()

    def test_name(self):
        params = {"name": ["name1", "name2"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_description(self):
        params = {
            "description": [
                "Test Record 1",
                "Test Record 2",
                "Test Record 3",
                "Test Record 4",
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_zone(self):
        params = {"zone": [self.zones[0]]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)
        params = {"zone_id": [self.zones[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_fqdn(self):
        params = {
            "fqdn": [
                "name1.zone1.example.com.",
                "name2.zone1.example.com.",
                "name4.zone1.example.com.",
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {
            "fqdn": [
                "name1.zone2.example.com.",
                "name2.zone2.example.com.",
                "name2.zone1.example.",
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_type(self):
        params = {"type": [RecordTypeChoices.A]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"type": [RecordTypeChoices.AAAA]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_status(self):
        params = {"status": [RecordStatusChoices.STATUS_INACTIVE]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"status": [RecordStatusChoices.STATUS_ACTIVE]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 8)

    def test_value(self):
        params = {"value": ["10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"value": ["fe80::dead:beef"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"value": ["fe80::dead:beef", "10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)

    def test_managed(self):
        params = {"managed": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)
        params = {"managed": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_tenant(self):
        params = {"tenant_id": [self.tenants[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"tenant": [self.tenants[1].slug]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_tenant_group(self):
        params = {"tenant_group_id": [self.tenant_groups[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"tenant_group": [self.tenant_groups[1].slug]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_ip_address(self):
        params = {"ip_address": ["fe80::dead:beef", "10.0.0.42", "1.2.3.4"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"ip_address": ["10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"ip_address": ["fe80::dead:beef"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_active(self):
        # *
        # Note: SOA records show up here as well!
        # -
        params = {"active": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"active": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)

    def test_ptr_record(self):
        Zone.objects.create(name="1.0.10.in-addr.arpa", **self.zone_data)
        address_record = Record.objects.create(
            name="name4",
            zone=self.zones[0],
            type=RecordTypeChoices.A,
            disable_ptr=False,
            value="10.0.1.42",
        )

        ptr_record = Record.objects.get(address_records=address_record)
        params = {"ptr_record_id": [ptr_record.pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        self.assertEqual(
            self.filterset(params, self.queryset).qs.first().pk, address_record.pk
        )

    def test_rfc2317_cname_record(self):
        Zone.objects.create(name="1.0.10.in-addr.arpa", **self.zone_data)

        Zone.objects.create(
            name="0-31.1.0.10.in-addr.arpa",
            rfc2317_prefix="10.0.1.0/27",
            rfc2317_parent_managed=True,
            **self.zone_data,
        )

        address_record = Record.objects.create(
            name="name4",
            zone=self.zones[0],
            type=RecordTypeChoices.A,
            disable_ptr=False,
            value="10.0.1.23",
        )

        ptr_record = Record.objects.get(address_records=address_record)
        cname_record = ptr_record.rfc2317_cname_record
        params = {"rfc2317_cname_record_id": [cname_record.pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        self.assertEqual(
            self.filterset(params, self.queryset).qs.first().pk, ptr_record.pk
        )
