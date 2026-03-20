from django.test import TestCase

from tenancy.models import Tenant, TenantGroup
from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import (
    Zone,
    View,
    NameServer,
    Registrar,
    RegistrationContact,
    DNSSECPolicy,
)
from netbox_dns.choices import ZoneStatusChoices, ZoneEPPStatusChoices

from netbox_dns.filtersets import ZoneFilterSet


class ZoneFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = Zone.objects.all()
    filterset = ZoneFilterSet

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
            View(name="View 1"),
            View(name="View 2"),
        )
        View.objects.bulk_create(cls.views)

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

        cls.dnssec_policies = (
            DNSSECPolicy(name="Test Policy 1", inline_signing=True),
            DNSSECPolicy(name="Test Policy 2", inline_signing=True),
            DNSSECPolicy(name="Test Policy 3", inline_signing=False),
        )
        DNSSECPolicy.objects.bulk_create(cls.dnssec_policies)

        cls.zones = (
            Zone(
                name="zone1.example.com",
                description="Test Zone 1",
                view=cls.views[0],
                tenant=cls.tenants[0],
                soa_ttl=86400,
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster.example.com",
                soa_refresh=43200,
                soa_retry=7200,
                soa_expire=2419200,
                soa_minimum=3600,
                soa_serial_auto=True,
                registry_domain_id="acme-001-4242",
                registrar=cls.registrars[0],
                registrant=cls.contacts[0],
                tech_c=cls.contacts[0],
                admin_c=cls.contacts[0],
                billing_c=cls.contacts[0],
                dnssec_policy=cls.dnssec_policies[0],
                parental_agents=["10.0.0.42", "2001:db8:dead:beef::23"],
                expiration_date="2025-04-01",
                domain_status=ZoneEPPStatusChoices.EPP_STATUS_CLIENT_TRANSFER_PROHIBITED,
            ),
            Zone(
                name="zone2.example.com",
                description="Test Zone 2",
                view=cls.views[0],
                tenant=cls.tenants[1],
                soa_ttl=86400,
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster.example.com",
                soa_refresh=43200,
                soa_retry=7200,
                soa_expire=2419200,
                soa_minimum=3600,
                soa_serial_auto=True,
                status=ZoneStatusChoices.STATUS_DEPRECATED,
                registry_domain_id="acme-001-2323",
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[0],
            ),
            Zone(
                name="zone3.example.com",
                description="Test Zone 3",
                view=cls.views[0],
                tenant=cls.tenants[2],
                soa_ttl=86400,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster2.example.com",
                soa_refresh=43200,
                soa_retry=7200,
                soa_expire=2419200,
                soa_minimum=3600,
                soa_serial_auto=True,
                registry_domain_id="acme-002-2323",
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[1],
                parental_agents=["10.0.0.23", "2001:db8:dead:beef::42"],
                expiration_date="2026-04-01",
                domain_status=ZoneEPPStatusChoices.EPP_STATUS_CLIENT_TRANSFER_PROHIBITED,
            ),
            Zone(
                name="zone1.example.com",
                description="Test Zone 4",
                view=cls.views[1],
                tenant=cls.tenants[0],
                soa_ttl=43200,
                soa_mname=cls.nameservers[0],
                soa_rname="hostmaster2.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
                registry_domain_id="acme-002-4242",
                registrar=cls.registrars[1],
                registrant=cls.contacts[1],
                tech_c=cls.contacts[1],
                admin_c=cls.contacts[1],
                billing_c=cls.contacts[1],
                dnssec_policy=cls.dnssec_policies[1],
            ),
            Zone(
                name="zone2.example.com",
                view=cls.views[1],
                tenant=cls.tenants[1],
                soa_ttl=43200,
                soa_mname=cls.nameservers[1],
                soa_rname="hostmaster2.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
                registry_domain_id="acme-003-4223",
                registrar=cls.registrars[2],
                registrant=cls.contacts[2],
                tech_c=cls.contacts[2],
                admin_c=cls.contacts[2],
                billing_c=cls.contacts[2],
                dnssec_policy=cls.dnssec_policies[2],
                parental_agents=["10.0.0.42", "2001:db8:dead:beef::42"],
                expiration_date="2025-04-01",
                domain_status=ZoneEPPStatusChoices.EPP_STATUS_INACTIVE,
            ),
            Zone(
                name="zone3.example.com",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster2.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
                registry_domain_id="acme-003-2342",
                registrar=cls.registrars[0],
                registrant=cls.contacts[2],
                tech_c=cls.contacts[2],
                admin_c=cls.contacts[2],
                billing_c=cls.contacts[2],
                dnssec_policy=cls.dnssec_policies[2],
                expiration_date="2026-04-01",
                domain_status=ZoneEPPStatusChoices.EPP_STATUS_INACTIVE,
            ),
            Zone(
                name="0.0.10.in-addr.arpa",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=True,
            ),
            Zone(
                name="1.0.10.in-addr.arpa",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=True,
            ),
            Zone(
                name="0-31.0.0.10.in-addr.arpa",
                view=cls.views[1],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
                rfc2317_prefix="10.0.0.0/27",
                rfc2317_parent_managed=True,
            ),
            Zone(
                name="32-63.0.0.10.in-addr.arpa",
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
                rfc2317_prefix="10.0.0.32/27",
            ),
            Zone(
                name="0.10.in-addr.arpa",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
            ),
            Zone(
                name="f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
            ),
            Zone(
                name="2.4.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa",
                view=cls.views[1],
                tenant=cls.tenants[2],
                soa_ttl=43200,
                soa_mname=cls.nameservers[2],
                soa_rname="hostmaster.example.com",
                soa_refresh=86400,
                soa_retry=3600,
                soa_expire=432000,
                soa_minimum=7200,
                soa_serial_auto=False,
            ),
        )
        for zone in cls.zones:
            zone.save()
        for i in range(3):
            cls.zones[i].nameservers.set([cls.nameservers[0].pk, cls.nameservers[1].pk])
        for i in range(3):
            cls.zones[3 + i].nameservers.set(
                [cls.nameservers[1].pk, cls.nameservers[2].pk]
            )

    def test_name(self):
        params = {"name": ["zone1.example.com", "zone2.example.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_description(self):
        params = {"description__regex": r"Test Zone [1-3]"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"description__empty": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_view(self):
        params = {"view": [self.views[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"view_id": [self.views[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_active(self):
        params = {"active": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 12)
        params = {"active": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

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
        params = {"soa_mname": ["ns1.example.com", "ns2.example.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"soa_mname_id": [self.nameservers[0].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_soa_rname(self):
        params = {"soa_rname__regex": r"hostmaster\..*"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 9)
        params = {"soa_rname__isw": "hostmaster2."}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

    def test_soa_serial(self):
        params = {"soa_serial__gt": 1000000}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)

    def test_soa_ttl(self):
        params = {"soa_ttl": 86400}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"soa_ttl": "P1D"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_refresh(self):
        params = {"soa_refresh": 86400}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 10)
        params = {"soa_refresh__lt": "P1D"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_retry(self):
        params = {"soa_retry": 7200}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"soa_retry__lt": "PT2H"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 10)

    def test_soa_expire(self):
        params = {"soa_expire": 432000}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 10)
        params = {"soa_expire__gt": "P5D"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_soa_minimum(self):
        params = {"soa_minimum": "PT1H"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"soa_minimum__gt": 3600}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 10)

    def test_arpa_network(self):
        params = {"arpa_network": ["fe80:dead:beef::/48", "10.0.0.0/24"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"arpa_network": ["fe80:dead:beef::/48", "10.0.1.0/24", "10.0.2.0/24"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_rfc2317_prefix(self):
        params = {"rfc2317_prefix": ["10.0.0.0/27"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"rfc2317_prefix": ["10.0.0.0/27", "10.0.0.32/27", "10.0.0.64/27"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_rfc2317_parent_zone(self):
        params = {"rfc2317_parent_zone": ["0.0.10.in-addr.arpa"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"rfc2317_parent_zone": ["0.10.in-addr.arpa"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)
        params = {"rfc2317_parent_zone_id": [self.zones[6].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_rfc2317_parent_managed(self):
        params = {"rfc2317_parent_managed": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 12)
        params = {"rfc2317_parent_managed": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_registrar(self):
        params = {"registrar": [self.registrars[1].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"registrar": [self.registrars[2].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {"registrar_id": [self.registrars[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)
        params = {"registrar_id": [self.registrars[2].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_registry_domain_id(self):
        params = {"registry_domain_id__regex": r"^acme-00[12]"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)

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

    def test_soa_serial_auto(self):
        params = {"soa_serial_auto": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 5)
        params = {"soa_serial_auto": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 8)

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
        params = {"parental_agents": ["10.0.0.42"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"parental_agents": ["10.0.0.23", "2001:db8:dead:beef::23"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_domain_status(self):
        params = {
            "domain_status": [
                ZoneEPPStatusChoices.EPP_STATUS_CLIENT_TRANSFER_PROHIBITED
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"domain_status": [ZoneEPPStatusChoices.EPP_STATUS_INACTIVE]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"domain_status": [ZoneEPPStatusChoices.EPP_STATUS_OK]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)

    def test_expiration_date(self):
        params = {"expiration_date_before": "2025-06-01"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"expiration_date_after": "2025-06-01"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"expiration_date_before": "2024-06-01"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)
        params = {"expiration_date_after": "2026-06-01"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)

    def test_inline_signing(self):
        params = {"inline_signing": True}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 4)
        params = {"inline_signing": False}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 9)
