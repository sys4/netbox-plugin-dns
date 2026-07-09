from rest_framework import status

from netbox.choices import CSVDelimiterChoices, ImportFormatChoices
from netbox_dns.choices import RecordStatusChoices, RecordTypeChoices, ZoneStatusChoices
from netbox_dns.models import (
    DNSSECPolicy,
    NameServer,
    Record,
    RecordTemplate,
    Registrar,
    RegistrationContact,
    View,
    Zone,
    ZoneTemplate,
)
from netbox_dns.tests.custom import ModelViewTestCase
from tenancy.models import Tenant
from utilities.testing import create_tags, post_data


def record_template_applied(record, record_template):
    if record.name != record_template.record_name:
        return False
    if record_template.tags and set(record.tags.all()) != set(
        record_template.tags.all()
    ):
        return False

    for field in RecordTemplate.template_fields:
        if getattr(record, field) != getattr(record_template, field):
            return False

    return True


class ZoneTemplatingViewTestCase(ModelViewTestCase):
    model = Zone

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.nameservers = (
            NameServer(name="ns1.example.com"),
            NameServer(name="ns2.example.com"),
            NameServer(name="ns3.example.com"),
            NameServer(name="ns4.example.com"),
            NameServer(name="ns5.example.com"),
            NameServer(name="ns6.example.com"),
        )
        NameServer.objects.bulk_create(cls.nameservers)

        cls.dnssec_policies = (
            DNSSECPolicy(name="Test Policy 1"),
            DNSSECPolicy(name="Test Policy 2"),
            DNSSECPolicy(name="Test Policy 3"),
        )
        DNSSECPolicy.objects.bulk_create(cls.dnssec_policies)

        cls.registrars = (
            Registrar(name="Registrar 1"),
            Registrar(name="Registrar 2"),
        )
        Registrar.objects.bulk_create(cls.registrars)

        cls.contacts = (
            RegistrationContact(contact_id="contact-1"),
            RegistrationContact(contact_id="contact-2"),
            RegistrationContact(contact_id="contact-3"),
            RegistrationContact(contact_id="contact-4"),
            RegistrationContact(contact_id="contact-5"),
        )
        RegistrationContact.objects.bulk_create(cls.contacts)

        cls.tenants = (
            Tenant(name="Peter", slug="peter"),
            Tenant(name="Paul", slug="paul"),
            Tenant(name="Mary", slug="mary"),
        )
        Tenant.objects.bulk_create(cls.tenants)

        cls.tags = create_tags("Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot")

        cls.zone_template = ZoneTemplate.objects.create(name="Zone Template 1")
        cls.zone_template.soa_mname = cls.nameservers[4]
        cls.zone_template.soa_rname = "hostmaster.example.com"
        cls.zone_template.tenant = cls.tenants[0]
        cls.zone_template.registrar = cls.registrars[0]
        cls.zone_template.registrant = cls.contacts[0]
        cls.zone_template.admin_c = cls.contacts[1]
        cls.zone_template.tech_c = cls.contacts[2]
        cls.zone_template.billing_c = cls.contacts[3]
        cls.zone_template.dnssec_policy = cls.dnssec_policies[0]
        # +
        # TODO: Causes an inexplicable error
        # -
        #       cls.zone_template.parental_agents = ["2001:db8:42::42", "2001:db8:23::23"]
        cls.zone_template.save()

        cls.zone_template.nameservers.set(cls.nameservers[0:3])
        cls.zone_template.tags.set(cls.tags[0:3])

        cls.zone_form_data = {
            "view": View.get_default_view().pk,
            "status": ZoneStatusChoices.STATUS_ACTIVE,
            **Zone.get_defaults(),
            "soa_serial_auto": False,
        }
        cls.zone_data = {
            "view": View.get_default_view(),
            "status": ZoneStatusChoices.STATUS_ACTIVE,
            **Zone.get_defaults(),
            "soa_serial_auto": False,
        }

        cls.record_templates = (
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
            RecordTemplate(
                name="Record Template 4",
                record_name="name1",
                type=RecordTypeChoices.AAAA,
                value="fe80:dead::beef:42",
                ttl=43200,
                disable_ptr=True,
                description="Test IPv6 address record",
                status=RecordStatusChoices.STATUS_INACTIVE,
                tenant=cls.tenants[0],
            ),
            RecordTemplate(
                name="Record Template 5",
                record_name="name1",
                type=RecordTypeChoices.AAAA,
                value="fe80:dead::beef:23",
                ttl=42,
                description="Test IPv6 address record (duplicate of 6)",
            ),
            RecordTemplate(
                name="Record Template 6",
                record_name="name1",
                type=RecordTypeChoices.AAAA,
                value="fe80:dead::beef:23",
                ttl=23,
                description="Test IPv6 address record (duplicate of 5)",
            ),
            RecordTemplate(
                name="Record Template 7",
                record_name="www",
                type=RecordTypeChoices.AAAA,
                value="fe80:dead::beef:815",
                description="Test IPv6 address record (conflicts with 2)",
            ),
        )
        RecordTemplate.objects.bulk_create(cls.record_templates)
        cls.record_templates[3].tags.set(cls.tags[0:3])

    def test_create_zone(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zones = Zone.objects.filter(name=request_data.get("name"))
        self.assertEqual(zones.count(), 1)
        zone = zones.first()

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.soa_mname, self.nameservers[4])
        self.assertEqual(zone.soa_rname, "hostmaster.example.com")
        self.assertEqual(zone.dnssec_policy, self.dnssec_policies[0])
        # +
        # TODO: Remove when/if the error above can be found
        # -
        #       self.assertEqual(zone.parental_agents, ["2001:db8:42::42", "2001:db8:23::23"])
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_create_zone_override_fields(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_dnssecpolicy",
            "netbox_dns.view_registrar",
            "netbox_dns.view_registrationcontact",
            "extras.view_tag",
            "tenancy.view_tenant",
        )

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "nameservers": [nameserver.pk for nameserver in self.nameservers[3:6]],
            "soa_mname": self.nameservers[5].pk,
            "soa_rname": "hostmaster2.example.com",
            "dnssec_policy": self.dnssec_policies[1].pk,
            "parental_agents": "2001:db8:42::23, 2001:db8:23::42",
            "registrar": self.registrars[1].pk,
            "registrant": self.contacts[4].pk,
            "tech_c": self.contacts[4].pk,
            "admin_c": self.contacts[4].pk,
            "billing_c": self.contacts[4].pk,
            "tenant": self.tenants[1].pk,
            "tags": [tag.pk for tag in self.tags[3:6]],
            **self.zone_form_data,
        }

        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zones = Zone.objects.filter(name=request_data.get("name"))
        self.assertEqual(zones.count(), 1)
        zone = zones.first()

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[3:6]))
        self.assertEqual(zone.soa_mname, self.nameservers[5])
        self.assertEqual(zone.soa_rname, "hostmaster2.example.com")
        self.assertEqual(zone.dnssec_policy, self.dnssec_policies[1])
        self.assertEqual(zone.parental_agents, ["2001:db8:42::23", "2001:db8:23::42"])
        self.assertEqual(set(zone.tags.all()), set(self.tags[3:6]))
        self.assertEqual(zone.tenant, self.tenants[1])
        self.assertEqual(zone.registrar, self.registrars[1])
        self.assertEqual(zone.registrant, self.contacts[4])
        self.assertEqual(zone.admin_c, self.contacts[4])
        self.assertEqual(zone.tech_c, self.contacts[4])
        self.assertEqual(zone.billing_c, self.contacts[4])

    def test_update_zone(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            **self.zone_data,
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
        )

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(zone.soa_mname, self.nameservers[4])
        self.assertEqual(zone.soa_rname, "hostmaster.example.com")
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_nameservers(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            **self.zone_data,
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
        )
        zone.nameservers.set(self.nameservers[3:6])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[3:6]))

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "nameservers": [nameserver.pk for nameserver in self.nameservers[3:6]],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[3:6]))

        self.assertEqual(zone.soa_mname, self.nameservers[4])
        self.assertEqual(zone.soa_rname, "hostmaster.example.com")
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_soa_mname(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            **self.zone_data,
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
        )

        self.assertEqual(zone.soa_mname, self.nameservers[5])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "soa_mname": self.nameservers[1],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.soa_mname, self.nameservers[1])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(zone.soa_rname, "hostmaster.example.com")
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_soa_rname(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            **self.zone_data,
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
        )

        self.assertEqual(zone.soa_mname, self.nameservers[5])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "soa_rname": "hostmaster3.example.com",
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.soa_rname, "hostmaster3.example.com")

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(zone.soa_mname, self.nameservers[4])
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_tags(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "extras.view_tag",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            **self.zone_data,
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
        )
        zone.tags.set(self.tags[3:6])

        self.assertEqual(set(zone.tags.all()), set(self.tags[3:6]))

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "tags": [tag.pk for tag in self.tags[3:6]],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(set(zone.tags.all()), set(self.tags[3:6]))

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_tenant(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "tenancy.view_tenant",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.tenant = self.tenants[1]
        zone.save

        self.assertEqual(zone.tenant, self.tenants[1])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "tenant": self.tenants[1],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.tenant, self.tenants[1])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_registrar(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_registrar",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.registrar = self.registrars[1]
        zone.save

        self.assertEqual(zone.registrar, self.registrars[1])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "registrar": self.registrars[1],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.registrar, self.registrars[1])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_registrant(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_registrationcontact",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.registrant = self.contacts[4]
        zone.save

        self.assertEqual(zone.registrant, self.contacts[4])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "registrant": self.contacts[4],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.registrant, self.contacts[4])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_tech_c(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_registrationcontact",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.tech_c = self.contacts[4]
        zone.save

        self.assertEqual(zone.tech_c, self.contacts[4])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "tech_c": self.contacts[4],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.tech_c, self.contacts[4])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_admin_c(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_registrationcontact",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.admin_c = self.contacts[4]
        zone.save

        self.assertEqual(zone.admin_c, self.contacts[4])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "admin_c": self.contacts[4],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.admin_c, self.contacts[4])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.tech_c, self.contacts[2])
        self.assertEqual(zone.billing_c, self.contacts[3])

    def test_update_zone_skip_existing_billing_c(self):
        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
            "netbox_dns.view_registrationcontact",
        )

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        zone.billing_c = self.contacts[4]
        zone.save

        self.assertEqual(zone.billing_c, self.contacts[4])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            "billing_c": self.contacts[4],
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zone.refresh_from_db()

        self.assertEqual(zone.billing_c, self.contacts[4])

        self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))
        self.assertEqual(set(zone.tags.all()), set(self.tags[0:3]))
        self.assertEqual(zone.tenant, self.tenants[0])
        self.assertEqual(zone.registrar, self.registrars[0])
        self.assertEqual(zone.registrant, self.contacts[0])
        self.assertEqual(zone.admin_c, self.contacts[1])
        self.assertEqual(zone.tech_c, self.contacts[2])

    def test_zone_bulk_import(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.nameservers.set(self.nameservers[0:3])

        path = self._get_url("bulk_import")
        csv_data = (
            "name,soa_mname,soa_rname,template",
            f"test1.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
            f"test2.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
            f"test3.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
        )
        request_data = {
            "format": ImportFormatChoices.CSV,
            "data": "\n".join(csv_data),
            "csv_delimiter": CSVDelimiterChoices.AUTO,
        }

        response = self.client.post(path, data=request_data)
        self.assertHttpStatus(response, 302)

        for line in csv_data[1:5]:
            zone_name = line.split(",")[0]
            zone = Zone.objects.get(name=zone_name)
            self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))

    def test_zone_bulk_update(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            # CSV rows carry an `id`, so this import updates existing zones,
            # which NetBox requires the change permission for.
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.nameservers.set(self.nameservers[0:3])

        zones = (
            Zone(
                name="test1.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
            Zone(
                name="test2.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
            Zone(
                name="test3.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
        )
        for zone in zones:
            zone.save()

        path = self._get_url("bulk_import")
        csv_data = (
            "id,template",
            f"{zones[0].id},{self.zone_template.name}",
            f"{zones[1].id},{self.zone_template.name}",
            f"{zones[2].id},{self.zone_template.name}",
        )
        request_data = {
            "format": ImportFormatChoices.CSV,
            "data": "\n".join(csv_data),
            "csv_delimiter": CSVDelimiterChoices.AUTO,
        }

        response = self.client.post(path, data=request_data)
        self.assertHttpStatus(response, 302)

        for zone in zones:
            self.assertEqual(set(zone.nameservers.all()), set(self.nameservers[0:3]))

    def test_zone_create_with_records(self):
        test_templates = self.record_templates[0:4]

        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zones = Zone.objects.filter(name=request_data.get("name"))
        self.assertEqual(zones.count(), 1)
        for record_template in test_templates:
            records = record_template.matching_records(zones.first())
            self.assertEqual(records.count(), 1)
            self.assertTrue(record_template_applied(records.first(), record_template))

    def test_zone_create_with_duplicate_records(self):
        test_templates = self.record_templates[4:6]

        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        zones = Zone.objects.filter(name=request_data.get("name"))
        self.assertEqual(zones.count(), 1)
        zone = zones.first()

        records = test_templates[0].matching_records(zone)
        self.assertEqual(records.count(), 1)

        self.assertTrue(record_template_applied(records.first(), test_templates[0]))
        self.assertFalse(record_template_applied(records.first(), test_templates[1]))

    def test_zone_create_with_conflicting_records(self):
        test_templates = (
            self.record_templates[1],
            self.record_templates[6],
        )

        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 200)
        self.assertRegex(
            response.content.decode(), "There is already an active CNAME record"
        )

        zones = Zone.objects.filter(name=request_data.get("name"))
        self.assertEqual(zones.count(), 0)

    def test_zone_update_with_records(self):
        test_templates = self.record_templates[0:4]

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )

        self.assertEqual(zone.records.count(), 1)  # SOA record

        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        self.assertEqual(zone.records.filter(managed=False).count(), 4)

        zone.refresh_from_db()

        for record_template in test_templates:
            records = record_template.matching_records(zone)
            self.assertEqual(records.count(), 1)
            self.assertTrue(record_template_applied(records.first(), record_template))

    def test_zone_update_with_existing_records(self):
        test_templates = self.record_templates[0:4]

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        existing_records = (
            Record(
                zone=zone,
                name=test_templates[0].record_name,
                type=test_templates[0].type,
                value=test_templates[0].value,
                ttl=42,
            ),
            Record(
                zone=zone,
                name=test_templates[1].record_name,
                type=test_templates[1].type,
                value=test_templates[1].value,
                ttl=42,
            ),
            Record(
                zone=zone,
                name=test_templates[2].record_name,
                type=test_templates[2].type,
                value=test_templates[2].value,
                ttl=42,
            ),
        )
        for record in existing_records:
            record.save()

        self.assertEqual(zone.records.filter(managed=False).count(), 3)

        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 302)

        self.assertEqual(zone.records.filter(managed=False).count(), 4)

        zone.refresh_from_db()
        for record_template in test_templates[0:3]:
            records = record_template.matching_records(zone)
            self.assertEqual(records.count(), 1)
            self.assertFalse(record_template_applied(records.first(), record_template))

        records = test_templates[3].matching_records(zone)
        self.assertEqual(records.count(), 1)
        self.assertTrue(record_template_applied(records.first(), test_templates[3]))

        for record in existing_records:
            record.refresh_from_db()
            self.assertEqual(record.ttl, 42)

    def test_zone_update_with_conflicting_records(self):
        test_template = self.record_templates[1]

        zone = Zone.objects.create(
            name="test.example.com",
            soa_mname=self.nameservers[5],
            soa_rname="hostmaster2.example.com",
            **self.zone_data,
        )
        Record.objects.create(
            zone=zone,
            name="www",
            type=RecordTypeChoices.AAAA,
            value="fe80:dead:beef::42:23",
        )

        self.assertEqual(zone.records.count(), 2)  # SOA record + existing record

        self.add_permissions(
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set([test_template])

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("edit", instance=zone),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, 200)
        self.assertEqual(zone.records.count(), 2)
        self.assertRegex(
            response.content.decode(),
            r"There is already an active record .* CNAME is not allowed",
        )

    def test_zone_bulk_import_with_records(self):
        test_templates = self.record_templates[0:3]

        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        path = self._get_url("bulk_import")
        csv_data = (
            "name,soa_mname,soa_rname,template",
            f"test1.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
            f"test2.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
            f"test3.example.com,ns1.example.com,hostmaster.example.com,{self.zone_template.name}",
        )
        request_data = {
            "format": ImportFormatChoices.CSV,
            "data": "\n".join(csv_data),
            "csv_delimiter": CSVDelimiterChoices.AUTO,
        }

        response = self.client.post(path, data=request_data)
        self.assertHttpStatus(response, 302)

        for line in csv_data[1:5]:
            zone_name = line.split(",")[0]
            zone = Zone.objects.get(name=zone_name)

            for record_template in test_templates:
                records = record_template.matching_records(zone)
                self.assertEqual(records.count(), 1)
                self.assertTrue(
                    record_template_applied(records.first(), record_template)
                )

    def test_zone_bulk_update_with_records(self):
        test_templates = self.record_templates[0:3]

        self.add_permissions(
            "netbox_dns.add_zone",
            # CSV rows carry an `id`, so this import updates existing zones,
            # which NetBox requires the change permission for.
            "netbox_dns.change_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.record_templates.set(test_templates)

        zones = (
            Zone(
                name="test1.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
            Zone(
                name="test2.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
            Zone(
                name="test3.example.com",
                soa_mname=self.nameservers[0],
                soa_rname="hostmaster.examplpe.com",
            ),
        )
        for zone in zones:
            zone.save()

        path = self._get_url("bulk_import")
        csv_data = (
            "id,template",
            f"{zones[0].id},{self.zone_template.name}",
            f"{zones[1].id},{self.zone_template.name}",
            f"{zones[2].id},{self.zone_template.name}",
        )
        request_data = {
            "format": ImportFormatChoices.CSV,
            "data": "\n".join(csv_data),
            "csv_delimiter": CSVDelimiterChoices.AUTO,
        }

        response = self.client.post(path, data=request_data)
        self.assertHttpStatus(response, 302)

        for zone in zones:
            for record_template in test_templates:
                records = record_template.matching_records(zone)
                self.assertEqual(records.count(), 1)
                self.assertTrue(
                    record_template_applied(records.first(), record_template)
                )

    def test_create_zone_missing_soa_mname(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.soa_mname = None
        self.zone_template.save()

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertIn(
            "soa_mname not set and no template or default value defined",
            response.content.decode(),
        )

    def test_create_zone_missing_soa_rname(self):
        self.add_permissions(
            "netbox_dns.add_zone",
            "netbox_dns.view_zonetemplate",
            "netbox_dns.view_view",
            "netbox_dns.view_nameserver",
        )

        self.zone_template.soa_rname = ""
        self.zone_template.save()

        request_data = {
            "name": "test.example.com",
            "template": self.zone_template.pk,
            **self.zone_form_data,
        }
        request = {
            "path": self._get_url("add"),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertIn(
            "soa_rname not set and no template or default value defined",
            response.content.decode(),
        )
