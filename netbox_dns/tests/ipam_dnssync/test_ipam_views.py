from unittest import skip

from django.core import management
from django.test import override_settings
from django.urls import reverse
from netaddr import IPNetwork
from rest_framework import status

from core.models import ObjectType
from extras.choices import CustomFieldTypeChoices
from extras.models import CustomField
from ipam.choices import IPAddressStatusChoices
from ipam.models import VRF, IPAddress, Prefix
from netbox_dns.choices import RecordTypeChoices
from netbox_dns.models import (
    NameServer,
    Record,
    View,
    Zone,
)
from netbox_dns.tests.custom import ModelViewTestCase
from utilities.testing import post_data


class DNSsyncIPAMViewTestCase(ModelViewTestCase):
    @classmethod
    def setUpTestData(cls):
        nameserver = NameServer.objects.create(name="ns1.example.com")

        cls.zone_data = {
            "soa_mname": nameserver,
            "soa_rname": "hostmaster.example.com.",
        }

        cls.default_ipaddress_data = {
            "status": IPAddressStatusChoices.STATUS_ACTIVE,
            "cf_ipaddress_dns_disabled": False,
            "cf_ipaddress_dns_record_disable_ptr": False,
        }

        cls.views = (
            View(name="view1"),
            View(name="view2"),
            View(name="view3"),
        )
        View.objects.bulk_create(cls.views)

        cls.zones = (
            Zone(name="zone1.example.com", view=cls.views[0], **cls.zone_data),
            Zone(name="zone2.example.com", view=cls.views[0], **cls.zone_data),
            Zone(name="example.com", view=cls.views[0], **cls.zone_data),
            Zone(name="zone1.example.com", view=cls.views[1], **cls.zone_data),
            Zone(name="zone2.example.com", view=cls.views[1], **cls.zone_data),
            Zone(name="example.com", view=cls.views[1], **cls.zone_data),
        )
        for zone in cls.zones:
            zone.save()

        cls.vrfs = (
            VRF(name="vrf1"),
            VRF(name="vrf2"),
        )
        VRF.objects.bulk_create(cls.vrfs)

        cls.prefixes = (
            Prefix(prefix="2001:db8::/48"),
            Prefix(prefix="2001:db8:1::/48"),
            Prefix(prefix="2001:db8:2::/48"),
            Prefix(prefix="2001:db8::/32"),
            Prefix(prefix="2001:db8::/48", vrf=cls.vrfs[0]),
            Prefix(prefix="2001:db8:1::/48", vrf=cls.vrfs[0]),
            Prefix(prefix="2001:db8:2::/48", vrf=cls.vrfs[0]),
            Prefix(prefix="2001:db8::/32", vrf=cls.vrfs[0]),
        )
        Prefix.objects.bulk_create(cls.prefixes)

        management.call_command("setup_dnssync", verbosity=0)

    def test_create_ipaddress(self):
        zone = self.zones[0]
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        ip_addresses = IPAddress.objects.filter(address=address)
        self.assertEqual(ip_addresses.count(), 1)
        ip_address = ip_addresses.first()

        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_create_ipaddress_ttl(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        self.add_permissions("ipam.add_ipaddress")
        self.add_permissions("netbox_dns.add_record")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_record_ttl": 86400,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        ip_address = IPAddress.objects.get(dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.ttl, 86400)

    def test_create_ipaddress_no_ptr(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        self.add_permissions("ipam.add_ipaddress")
        self.add_permissions("netbox_dns.add_record")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_record_disable_ptr": True,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        ip_address = IPAddress.objects.get(dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.disable_ptr, True)

    def test_create_ipaddress_no_dns(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        self.add_permissions("ipam.add_ipaddress")
        self.add_permissions("netbox_dns.add_record")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_disabled": True,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        ip_address = IPAddress.objects.get(dns_name=name)
        self.assertFalse(Record.objects.filter(type=RecordTypeChoices.AAAA).exists())
        self.assertFalse(ip_address.netbox_dns_records.exists())

    def test_create_ipaddress_duplicate_record(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        Record.objects.create(
            name="name1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value=address.split("/")[0],
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active AAAA record"
        )

        self.assertFalse(IPAddress.objects.filter(dns_name=name).exists())
        self.assertFalse(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).exists()
        )

    @override_settings(ENFORCE_GLOBAL_UNIQUE=False)
    def test_create_duplicate_ipaddress(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        IPAddress.objects.create(address=IPNetwork(address), dns_name=name)

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "Unique DNS records are enforced and there is already an active IP address",
        )

        self.assertEqual(IPAddress.objects.filter(dns_name=name).count(), 1)
        self.assertEqual(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).count(), 1
        )

    @override_settings(ENFORCE_GLOBAL_UNIQUE=False)
    def test_create_duplicate_ipaddress_existing_inactive(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        IPAddress.objects.create(
            address=IPNetwork(address),
            dns_name=name,
            status=IPAddressStatusChoices.STATUS_RESERVED,
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertEqual(IPAddress.objects.filter(dns_name=name).count(), 2)
        self.assertEqual(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).count(), 2
        )

    @override_settings(ENFORCE_GLOBAL_UNIQUE=False)
    def test_create_duplicate_ipaddress_new_inactive(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        IPAddress.objects.create(address=IPNetwork(address), dns_name=name)

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "status": IPAddressStatusChoices.STATUS_RESERVED,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertEqual(IPAddress.objects.filter(dns_name=name).count(), 2)
        self.assertEqual(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).count(), 2
        )

    @override_settings(ENFORCE_GLOBAL_UNIQUE=False)
    def test_create_duplicate_ipaddress_existing_dns_disabled(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        IPAddress.objects.create(
            address=IPNetwork(address),
            dns_name=name,
            custom_field_data={
                "ipaddress_dns_disabled": True,
            },
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertEqual(IPAddress.objects.filter(dns_name=name).count(), 2)
        self.assertEqual(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).count(), 1
        )

    @override_settings(ENFORCE_GLOBAL_UNIQUE=False)
    def test_create_duplicate_ipaddress_new_dns_disabled(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        IPAddress.objects.create(
            address=IPNetwork(address),
            dns_name=name,
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_disabled": True,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertEqual(IPAddress.objects.filter(dns_name=name).count(), 2)
        self.assertEqual(
            Record.objects.filter(type=RecordTypeChoices.AAAA, managed=True).count(), 1
        )

    def test_create_ipaddress_invalid_record(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        Record.objects.create(
            name="name1", zone=zone, type=RecordTypeChoices.CNAME, value="@"
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active CNAME record"
        )

        self.assertFalse(IPAddress.objects.filter(dns_name=name).exists())
        self.assertFalse(Record.objects.filter(type=RecordTypeChoices.AAAA).exists())

    def test_create_ipaddress_invalid_record_filter(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        cf = CustomField.objects.create(
            name="ipaddress_dns",
            type=CustomFieldTypeChoices.TYPE_BOOLEAN,
            default=False,
            required=False,
        )
        cf.object_types.set([ObjectType.objects.get_for_model(IPAddress)])

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)
        view.ip_address_filter = {"custom_field_data__ipaddress_dns": True}
        view.save()

        Record.objects.create(
            name="name1", zone=zone, type=RecordTypeChoices.CNAME, value="@"
        )

        self.add_permissions("ipam.add_ipaddress")

        url = reverse("ipam:ipaddress_add")

        request_data = {
            "address": address,
            "dns_name": name,
            "cf_ipaddress_dns": True,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active CNAME record"
        )

        self.assertFalse(IPAddress.objects.filter(dns_name=name).exists())
        self.assertFalse(Record.objects.filter(type=RecordTypeChoices.AAAA).exists())

    def test_update_ipaddress_name(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name1 = "name1.zone1.example.com"
        name2 = "name2.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address), dns_name=name1
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name2,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name2}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_update_ipaddress_address(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address1 = "2001:db8::1/64"
        address2 = "2001:db8::2/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address1), dns_name=name
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address2,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address2.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_update_ipaddress_name_different_zone(self):
        view = self.views[0]
        zone = self.zones[1]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name1 = "name1.zone1.example.com"
        name2 = "name1.zone2.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address), dns_name=name1
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name2,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name2}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_update_ipaddress_address_different_view(self):
        view1 = self.views[0]
        view2 = self.views[1]
        zone1 = self.zones[0]
        zone2 = self.zones[3]
        prefix1 = self.prefixes[0]
        prefix2 = self.prefixes[1]

        address1 = "2001:db8::1/64"
        address2 = "2001:db8:1::1/64"
        name = "name1.zone1.example.com"

        view1.prefixes.add(prefix1)
        view2.prefixes.add(prefix2)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address1), dns_name=name
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address1.split("/")[0])
        self.assertEqual(record.zone, zone1)

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address2,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address2.split("/")[0])
        self.assertEqual(record.zone, zone2)

    def test_update_ipaddress_address_no_view(self):
        view1 = self.views[0]
        view2 = self.views[2]
        zone = self.zones[0]
        prefix1 = self.prefixes[0]
        prefix2 = self.prefixes[1]

        address1 = "2001:db8::1/64"
        address2 = "2001:db8:1::1/64"
        name = "name1.zone1.example.com"

        view1.prefixes.add(prefix1)
        view2.prefixes.add(prefix2)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address1), dns_name=name
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address1.split("/")[0])
        self.assertEqual(record.zone, zone)

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address2,
            "dns_name": name,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertFalse(Record.objects.filter(type=RecordTypeChoices.AAAA).exists())
        self.assertFalse(ip_address.netbox_dns_records.exists())

    def test_update_ipaddress_vrf_different_view(self):
        view1 = self.views[0]
        view2 = self.views[1]
        zone1 = self.zones[0]
        zone2 = self.zones[3]
        prefix1 = self.prefixes[0]
        prefix2 = self.prefixes[4]
        vrf = self.vrfs[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view1.prefixes.add(prefix1)
        view2.prefixes.add(prefix2)

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone1)

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("ipam.view_vrf")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            "vrf": vrf.pk,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone2)

    def test_update_ipaddress_vrf_no_view(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]
        vrf = self.vrfs[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("ipam.view_vrf")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            "vrf": vrf.pk,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertFalse(Record.objects.filter(type=RecordTypeChoices.AAAA).exists())
        self.assertFalse(ip_address.netbox_dns_records.exists())

    def test_update_ipaddress_ttl(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address1 = "2001:db8::1/64"
        address2 = "2001:db8::2/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address1 = IPAddress.objects.create(
            address=IPNetwork(address1), dns_name=name
        )
        ip_address2 = IPAddress.objects.create(
            address=IPNetwork(address2), dns_name=name
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address1).exists())
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address2).exists())
        self.assertEqual(
            Record.objects.get(ipam_ip_address=ip_address1).ttl,
            Record.objects.get(ipam_ip_address=ip_address2).ttl,
        )

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("netbox_dns.add_record")
        self.add_permissions("netbox_dns.change_record")
        self.add_permissions("netbox_dns.delete_record")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address1.pk})

        request_data = {
            "address": address1,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_record_ttl": 86400,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address1)
        self.assertEqual(record.ttl, 86400)

    def test_update_ipaddress_disable_ptr(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("netbox_dns.add_record")
        self.add_permissions("netbox_dns.change_record")
        self.add_permissions("netbox_dns.delete_record")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_record_disable_ptr": True,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertTrue(record.disable_ptr)

    def test_update_ipaddress_disable_dnssync(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("netbox_dns.add_record")
        self.add_permissions("netbox_dns.change_record")
        self.add_permissions("netbox_dns.delete_record")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_disabled": True,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertFalse(Record.objects.filter(ipam_ip_address=ip_address).exists())

    def test_update_ipaddress_enable_dnssync(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address),
            dns_name=name,
            custom_field_data={"ipaddress_dns_disabled": True},
        )
        self.assertFalse(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions("ipam.change_ipaddress")
        self.add_permissions("netbox_dns.add_record")
        self.add_permissions("netbox_dns.change_record")
        self.add_permissions("netbox_dns.delete_record")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            **self.default_ipaddress_data,
            "cf_ipaddress_dns_disabled": False,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

    def test_update_ipaddress_name_duplicate_record(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name1 = "name1.zone1.example.com"
        name2 = "name2.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address), dns_name=name1
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        Record.objects.create(
            name="name2",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value=address.split("/")[0],
        )

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name2,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active AAAA record"
        )

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name1}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_update_ipaddress_name_invalid_record(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name1 = "name1.zone1.example.com"
        name2 = "name2.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address), dns_name=name1
        )
        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        Record.objects.create(
            name="name2", zone=zone, type=RecordTypeChoices.CNAME, value="@"
        )

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name2,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active CNAME record"
        )

        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name1}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

    def test_update_ipaddress_cf_invalid_record_filter(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        cf = CustomField.objects.create(
            name="ipaddress_dns",
            type=CustomFieldTypeChoices.TYPE_BOOLEAN,
            default=False,
            required=False,
        )
        cf.object_types.set([ObjectType.objects.get_for_model(IPAddress)])

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)
        view.ip_address_filter = {"custom_field_data__ipaddress_dns": True}
        view.save()

        ip_address = IPAddress.objects.create(
            address=IPNetwork(address),
            dns_name=name,
            custom_field_data={"ipaddress_dns": False},
        )
        self.assertFalse(Record.objects.filter(ipam_ip_address=ip_address).exists())

        Record.objects.create(
            name="name1", zone=zone, type=RecordTypeChoices.CNAME, value="@"
        )

        self.add_permissions("ipam.change_ipaddress")

        url = reverse("ipam:ipaddress_edit", kwargs={"pk": ip_address.pk})

        request_data = {
            "address": address,
            "dns_name": name,
            "cf_ipaddress_dns": True,
            **self.default_ipaddress_data,
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active CNAME record"
        )

        self.assertFalse(Record.objects.filter(ipam_ip_address=ip_address).exists())

    def test_update_prefix_assign_view(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        self.add_permissions(
            "ipam.view_prefix",
            "ipam.change_prefix",
            "netbox_dns.change_view",
            "netbox_dns.view_view",
        )

        url = reverse("ipam:prefix_views", kwargs={"pk": prefix.pk})

        request_data = {
            "views": [view.pk],
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertIn(view, prefix.netbox_dns_views.all())
        self.assertIn(prefix, view.prefixes.all())

    def test_update_prefix_assign_view_conflict(self):
        view = self.views[0]
        prefix = self.prefixes[0]
        zone = self.zones[0]

        name = "name1.zone1.example.com"
        address = "2001:db8::1/64"

        Record.objects.create(
            name="name1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value=address.split("/")[0],
        )
        IPAddress.objects.create(address=IPNetwork(address), dns_name=name)

        self.add_permissions(
            "ipam.view_prefix",
            "ipam.change_prefix",
            "netbox_dns.change_view",
            "netbox_dns.view_view",
        )

        url = reverse("ipam:prefix_views", kwargs={"pk": prefix.pk})

        request_data = {
            "views": [view.pk],
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active AAAA record"
        )

        self.assertNotIn(view, prefix.netbox_dns_views.all())
        self.assertNotIn(prefix, view.prefixes.all())

    @skip("TBD: Fails with NetBox 4.7.0b1")
    def test_update_prefix_remove_view(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        view.prefixes.add(prefix)

        name = "name1.zone1.example.com"
        address = "2001:db8::1/64"

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)

        self.assertTrue(Record.objects.filter(ipam_ip_address=ip_address).exists())

        self.add_permissions(
            "ipam.view_prefix",
            "ipam.change_prefix",
            "netbox_dns.change_view",
            "netbox_dns.view_view",
        )

        url = reverse("ipam:prefix_views", kwargs={"pk": prefix.pk})

        request_data = {
            "views": [],
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertNotIn(view, prefix.netbox_dns_views.all())
        self.assertNotIn(prefix, view.prefixes.all())
        self.assertFalse(Record.objects.filter(ipam_ip_address=ip_address).exists())

    def test_update_prefix_remove_view_conflict(self):
        view1 = self.views[0]
        view2 = self.views[1]
        prefix1 = self.prefixes[0]
        prefix2 = self.prefixes[3]
        zone1 = self.zones[0]
        zone2 = self.zones[3]

        view1.prefixes.add(prefix1)
        view2.prefixes.add(prefix2)

        name = "name1.zone1.example.com"
        address = "2001:db8::1/64"

        Record.objects.create(
            name="name1",
            zone=zone2,
            type=RecordTypeChoices.AAAA,
            value=address.split("/")[0],
        )
        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)

        self.assertTrue(
            Record.objects.filter(ipam_ip_address=ip_address, zone=zone1).exists()
        )

        self.add_permissions(
            "ipam.view_prefix",
            "ipam.change_prefix",
            "netbox_dns.change_view",
            "netbox_dns.view_view",
        )

        url = reverse("ipam:prefix_views", kwargs={"pk": prefix1.pk})

        request_data = {
            "views": [],
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(), "There is already an active AAAA record"
        )

        self.assertIn(view1, prefix1.netbox_dns_views.all())
        self.assertIn(prefix1, view1.prefixes.all())
        self.assertTrue(
            Record.objects.filter(ipam_ip_address=ip_address, zone=zone1).exists()
        )

    def test_update_prefix_assign_view_insufficient_permissions(self):
        view = self.views[0]
        prefix = self.prefixes[0]

        self.add_permissions(
            "ipam.view_prefix", "ipam.change_prefix", "netbox_dns.view_view"
        )

        url = reverse("ipam:prefix_views", kwargs={"pk": prefix.pk})

        request_data = {
            "views": [view.pk],
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "You do not have permission to modify assigned views",
        )

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertNotIn(view, prefix.netbox_dns_views.all())
        self.assertNotIn(prefix, view.prefixes.all())

    def test_delete_ipaddress(self):
        view = self.views[0]
        zone = self.zones[0]
        prefix = self.prefixes[0]

        address = "2001:db8::1/64"
        name = "name1.zone1.example.com"

        view.prefixes.add(prefix)

        ip_address = IPAddress.objects.create(address=IPNetwork(address), dns_name=name)
        record = Record.objects.get(ipam_ip_address=ip_address)
        self.assertEqual(record.type, RecordTypeChoices.AAAA)
        self.assertEqual(record.fqdn, f"{name}.")
        self.assertEqual(record.value, address.split("/")[0])
        self.assertEqual(record.zone, zone)

        self.add_permissions("ipam.delete_ipaddress")

        url = reverse("ipam:ipaddress_delete", kwargs={"pk": ip_address.pk})

        request = {
            "data": {"confirm": True},
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        self.assertFalse(Record.objects.filter(pk=record.pk).exists())
