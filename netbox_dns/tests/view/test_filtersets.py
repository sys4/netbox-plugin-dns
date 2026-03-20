from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from ipam.models import Prefix
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import View
from netbox_dns.filtersets import ViewFilterSet


class ViewFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = View.objects.all()
    filterset = ViewFilterSet
    ignore_fields = ("ip_address_filter",)

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

        cls.views = (
            View(name="View 1", description="Test View 1", tenant=cls.tenants[0]),
            View(name="View 2", description="Test View 2", tenant=cls.tenants[1]),
            View(name="View 3", description="Test View 3", tenant=cls.tenants[2]),
        )
        View.objects.bulk_create(cls.views)

    def test_name(self):
        params = {"name": ["View 1", "View 2"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_description(self):
        params = {"description": ["Test View 1", "Test View 2"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_default_view(self):
        params = {"default_view": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"default_view": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

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

    def test_prefixes(self):
        prefixes = (
            Prefix(prefix="10.13.1.0/24"),
            Prefix(prefix="10.23.1.0/24"),
            Prefix(prefix="10.37.1.0/24"),
            Prefix(prefix="10.42.1.0/24"),
        )
        Prefix.objects.bulk_create(prefixes)

        self.views[0].prefixes.set(prefixes[0:2])
        self.views[1].prefixes.set(prefixes[2:4])
        self.views[2].prefixes.set(prefixes[0:4])

        params = {"prefix_id": [prefix.pk for prefix in prefixes[0:2]]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"prefix_id": [prefix.pk for prefix in prefixes[0:4]]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"prefix": [prefix.prefix for prefix in prefixes[0:2]]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"prefix": [prefixes[3].prefix]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
