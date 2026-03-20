from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import RecordTemplate, ZoneTemplate
from netbox_dns.choices import RecordTypeChoices, RecordStatusChoices
from netbox_dns.filtersets import RecordTemplateFilterSet


class RecordTemplateFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = RecordTemplate.objects.all()
    filterset = RecordTemplateFilterSet

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

        cls.record_templates = (
            RecordTemplate(
                name="Test Record Template 1",
                description="Test Record Template 1",
                record_name="name1",
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[0],
            ),
            RecordTemplate(
                name="Test Record Template 2",
                description="Test Record Template 2",
                record_name="name2",
                type=RecordTypeChoices.A,
                value="10.0.0.42",
                status=RecordStatusChoices.STATUS_INACTIVE,
                tenant=cls.tenants[0],
            ),
            RecordTemplate(
                name="Test Record Template 3",
                description="Test Record Template 3",
                record_name="name3",
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                tenant=cls.tenants[1],
            ),
            RecordTemplate(
                name="Test Record Template 4",
                description="Test Record Template 4",
                record_name="name1",
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                disable_ptr=True,
                tenant=cls.tenants[0],
            ),
            RecordTemplate(
                name="Test Record Template 5",
                description="Test Record Template 5",
                record_name="name2",
                type=RecordTypeChoices.A,
                value="10.0.0.42",
                tenant=cls.tenants[0],
            ),
            RecordTemplate(
                name="Test Record Template 6",
                description="Test Record Template 6",
                record_name="name3",
                type=RecordTypeChoices.AAAA,
                value="fe80::dead:beef",
                status=RecordStatusChoices.STATUS_INACTIVE,
                disable_ptr=True,
                tenant=cls.tenants[1],
            ),
        )
        RecordTemplate.objects.bulk_create(cls.record_templates)

        cls.zone_templates = (
            ZoneTemplate(name="Zone Template 1"),
            ZoneTemplate(name="Zone Template 2"),
            ZoneTemplate(name="Zone Template 3"),
        )
        ZoneTemplate.objects.bulk_create(cls.zone_templates)
        cls.zone_templates[0].record_templates.set(cls.record_templates[0:3])
        cls.zone_templates[1].record_templates.set(cls.record_templates[0:6])
        cls.zone_templates[2].record_templates.set(cls.record_templates[3:6])

    def test_name(self):
        params = {"name": ["Test Record Template 1", "Test Record Template 3"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_description(self):
        params = {"description__regex": r"Test Record Template [12]"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_record_name(self):
        params = {"record_name": ["name1", "name3"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_type(self):
        params = {"type": [RecordTypeChoices.A]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"type": [RecordTypeChoices.AAAA]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_value(self):
        params = {"value": ["10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"value": ["fe80::dead:beef"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"value": ["fe80::dead:beef", "10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)

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

    def test_status(self):
        params = {"status": [RecordStatusChoices.STATUS_ACTIVE]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"status": [RecordStatusChoices.STATUS_INACTIVE]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_disable_ptr(self):
        params = {"disable_ptr": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"disable_ptr": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_zone_template(self):
        params = {"zone_template": [self.zone_templates[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"zone_template": [self.zone_templates[1].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"zone_template": [self.zone_templates[2].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"zone_template_id": [self.zone_templates[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"zone_template_id": [self.zone_templates[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"zone_template_id": [self.zone_templates[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
