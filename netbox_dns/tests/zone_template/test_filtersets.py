from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import (
    ZoneTemplate,
    RecordTemplate,
    NameServer,
    Registrar,
    RegistrationContact,
    DNSSECPolicy,
)
from netbox_dns.choices import RecordTypeChoices
from netbox_dns.filtersets import ZoneTemplateFilterSet


class ZoneTemplateFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = ZoneTemplate.objects.all()
    filterset = ZoneTemplateFilterSet

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
            NameServer(name="ns1.example.com"),
            NameServer(name="ns2.example.com"),
            NameServer(name="ns3.example.com"),
        )
        NameServer.objects.bulk_create(cls.nameservers)

        cls.registrars = (
            Registrar(name="ACME 2 Corporation", iana_id=4242),
            Registrar(name="ACME 2 Limited", iana_id=2323),
            Registrar(name="ACME 2 Trust", iana_id=55),
        )
        Registrar.objects.bulk_create(cls.registrars)

        cls.contacts = (
            RegistrationContact(name="Paul Example", contact_id="4242"),
            RegistrationContact(name="Fred Example", contact_id="2323"),
            RegistrationContact(name="Jack Example", contact_id="0815"),
        )
        RegistrationContact.objects.bulk_create(cls.contacts)

        cls.record_templates = [
            RecordTemplate(
                name="Record Template 1",
                record_name="@",
                type=RecordTypeChoices.MX,
                value="10 mx1.example.com.",
            ),
            RecordTemplate(
                name="Record Template 2",
                record_name="www",
                type=RecordTypeChoices.CNAME,
                value="@",
            ),
            RecordTemplate(
                name="Record Template 3",
                record_name="@",
                type=RecordTypeChoices.TXT,
                value="v=spf1 +mx -all",
            ),
        ]
        RecordTemplate.objects.bulk_create(cls.record_templates)

        cls.dnssec_policies = (
            DNSSECPolicy(name="Test Policy 1"),
            DNSSECPolicy(name="Test Policy 2"),
            DNSSECPolicy(name="Test Policy 3"),
        )
        DNSSECPolicy.objects.bulk_create(cls.dnssec_policies)

        cls.zone_templates = (
            ZoneTemplate(
                name="Zone Template 1",
                description="Test Zone Template 1",
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster.example.com",
                tenant=cls.tenants[0],
                registrar=cls.registrars[0],
                registrant=cls.contacts[0],
                tech_c=cls.contacts[0],
                admin_c=cls.contacts[0],
                billing_c=cls.contacts[0],
                dnssec_policy=cls.dnssec_policies[0],
                parental_agents=["2001:db8:42::42", "2001:db8:23::23"],
            ),
            ZoneTemplate(
                name="Zone Template 2",
                description="Test Zone Template 2",
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster2.example.com",
                tenant=cls.tenants[1],
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[0],
                parental_agents=["2001:db8:42::42", "2001:db8:42::23"],
            ),
            ZoneTemplate(
                name="Zone Template 3",
                description="Test Zone Template 3",
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster.example.com",
                tenant=cls.tenants[2],
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[1],
                parental_agents=["2001:db8:42::42", "2001:db8:42::23"],
            ),
            ZoneTemplate(
                name="Zone Template 4",
                description="Test Zone Template 4",
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster2.example.com",
                tenant=cls.tenants[0],
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[1],
                parental_agents=["2001:db8:42::42", "2001:db8:23::23"],
            ),
            ZoneTemplate(
                name="Zone Template 5",
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster.example.com",
                tenant=cls.tenants[1],
                registrar=cls.registrars[2],
                registrant=cls.contacts[2],
                tech_c=cls.contacts[2],
                admin_c=cls.contacts[2],
                billing_c=cls.contacts[2],
                dnssec_policy=cls.dnssec_policies[2],
            ),
            ZoneTemplate(
                name="Zone Template 6",
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster2.example.com",
                tenant=cls.tenants[2],
                registrar=cls.registrars[0],
                registrant=cls.contacts[2],
                tech_c=cls.contacts[2],
                admin_c=cls.contacts[2],
                billing_c=cls.contacts[2],
                dnssec_policy=cls.dnssec_policies[2],
            ),
        )
        ZoneTemplate.objects.bulk_create(cls.zone_templates)
        for i in range(3):
            cls.zone_templates[i].nameservers.set(
                [cls.nameservers[0].pk, cls.nameservers[1].pk]
            )
            cls.zone_templates[i].record_templates.set(
                [cls.record_templates[0].pk, cls.record_templates[1].pk]
            )
        for i in range(3):
            cls.zone_templates[3 + i].nameservers.set(
                [cls.nameservers[1].pk, cls.nameservers[2].pk]
            )
            cls.zone_templates[3 + i].record_templates.set(
                [cls.record_templates[1].pk, cls.record_templates[2].pk]
            )

    def test_name(self):
        params = {"name": ["Zone Template 1", "Zone Template 3"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_descirption(self):
        params = {
            "description": [
                "Test Zone Template 1",
                "Test Zone Template 2",
                "Test Zone Template 9",
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_nameserver(self):
        params = {"nameserver": [self.nameservers[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"nameserver": [self.nameservers[1].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"nameserver": [self.nameservers[2].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"nameserver_id": [self.nameservers[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"nameserver_id": [self.nameservers[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"nameserver_id": [self.nameservers[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_mname(self):
        params = {"soa_mname": [self.nameservers[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"soa_mname_id": [self.nameservers[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_rname(self):
        params = {"soa_rname": ["hostmaster.example.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_record_template(self):
        params = {"record_template": [self.record_templates[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"record_template": [self.record_templates[1].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"record_template": [self.record_templates[2].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"record_template_id": [self.record_templates[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"record_template_id": [self.record_templates[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 6)
        params = {"record_template_id": [self.record_templates[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_registrar(self):
        params = {"registrar": [self.registrars[1].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"registrar": [self.registrars[2].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"registrar_id": [self.registrars[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"registrar_id": [self.registrars[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_registrant(self):
        params = {"registrant": [self.contacts[1].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"registrant_id": [self.contacts[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_admin_c(self):
        params = {"admin_c": [self.contacts[1].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"admin_c_id": [self.contacts[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_tech_c(self):
        params = {"tech_c": [self.contacts[2].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"tech_c": [self.contacts[0].contact_id, self.contacts[1].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"tech_c_id": [self.contacts[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"tech_c_id": [self.contacts[0].pk, self.contacts[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_billing_c(self):
        params = {"billing_c": [self.contacts[0].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"billing_c": [self.contacts[1].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"billing_c": [self.contacts[2].contact_id]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {
            "billing_c": [self.contacts[1].contact_id, self.contacts[2].contact_id]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)
        params = {"billing_c_id": [self.contacts[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"billing_c_id": [self.contacts[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_dnssec_policy(self):
        params = {
            "dnssec_policy_id": [self.dnssec_policies[0].pk, self.dnssec_policies[1].pk]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {
            "dnssec_policy": [
                self.dnssec_policies[0].name,
                self.dnssec_policies[1].name,
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_parental_agents(self):
        params = {"parental_agents": ["2001:db8:23::23", "2001:db8:42::42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"parental_agents": ["2001:db8:23::23"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_tenant(self):
        params = {"tenant_id": [self.tenants[0].pk, self.tenants[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"tenant": [self.tenants[0].slug, self.tenants[1].slug]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_tenant_group(self):
        params = {
            "tenant_group_id": [self.tenant_groups[0].pk, self.tenant_groups[1].pk]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {
            "tenant_group": [self.tenant_groups[0].slug, self.tenant_groups[1].slug]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
