from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import NameServer, Zone
from netbox_dns.filtersets import NameServerFilterSet


class NameServerFiterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = NameServer.objects.all()
    filterset = NameServerFilterSet

    @classmethod
    def setUpTestData(cls):
        cls.tenant_groups = (
            TenantGroup(name="Tenant group 1", slug="tenant-group-1"),
            TenantGroup(name="Tenant group 2", slug="tenant-group-2"),
            TenantGroup(name="Tenant group 3", slug="tenant-group-3"),
        )
        for tenantgroup in cls.tenant_groups:
            tenantgroup.save()

        cls.tenants = (
            Tenant(name="Tenant 1", slug="tenant-1", group=cls.tenant_groups[0]),
            Tenant(name="Tenant 2", slug="tenant-2", group=cls.tenant_groups[1]),
            Tenant(name="Tenant 3", slug="tenant-3", group=cls.tenant_groups[2]),
        )
        Tenant.objects.bulk_create(cls.tenants)

        cls.nameservers = (
            NameServer(
                name="ns1.example.com",
                description="Test Name Server 1",
                tenant=cls.tenants[0],
            ),
            NameServer(
                name="ns2.example.com",
                description="Test Name Server 2",
                tenant=cls.tenants[1],
            ),
            NameServer(
                name="ns3.example.com",
                description="Test Name Server 3",
                tenant=cls.tenants[2],
            ),
        )
        for nameserver in cls.nameservers:
            nameserver.save()

        cls.zones = (
            Zone(
                name="zone1.example.com",
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster.example.com",
            ),
            Zone(
                name="zone2.example.com",
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster.example.com",
            ),
            Zone(
                name="zone3.example.com",
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster.example.com",
            ),
        )
        for zone in cls.zones:
            zone.save()
        cls.zones[0].nameservers.add(cls.nameservers[0], cls.nameservers[1])
        cls.zones[1].nameservers.add(cls.nameservers[1], cls.nameservers[2])
        cls.zones[2].nameservers.add(
            cls.nameservers[0], cls.nameservers[1], cls.nameservers[2]
        )

    def test_name(self):
        params = {"name": ["ns1.example.com", "ns2.example.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_description(self):
        params = {"description": ["Test Name Server 2", "Test Name Server 3"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_tenant(self):
        params = {"tenant_id": [self.tenants[0].pk, self.tenants[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"tenant": [self.tenants[0].slug, self.tenants[1].slug]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_tenant_group(self):
        params = {
            "tenant_group_id": [self.tenant_groups[0].pk, self.tenant_groups[1].pk]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {
            "tenant_group": [self.tenant_groups[0].slug, self.tenant_groups[1].slug]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_zones(self):
        params = {"zone_id": [self.zones[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"zone_id": [self.zones[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"zone_id": [self.zones[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_zones(self):
        params = {"soa_zone_id": [self.zones[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        self.assertEqual(
            self.filterset(params, self.queryset).qs.first().pk, self.nameservers[0].pk
        )
        params = {"soa_zone_id": [self.zones[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        self.assertEqual(
            self.filterset(params, self.queryset).qs.first().pk, self.nameservers[0].pk
        )
        params = {"soa_zone_id": [self.zones[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        self.assertEqual(
            self.filterset(params, self.queryset).qs.first().pk, self.nameservers[1].pk
        )
        params = {"soa_zone_id": [self.zones[0].pk, self.zones[2].pk, self.zones[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
