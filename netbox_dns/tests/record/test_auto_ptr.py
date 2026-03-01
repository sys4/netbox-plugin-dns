import ipaddress

from django.test import TestCase, override_settings

from netbox_dns.models import NameServer, Record, Zone
from netbox_dns.choices import RecordTypeChoices, RecordStatusChoices


def reverse_name(address, reverse_zone):
    reverse_pointer = ipaddress.ip_address(address).reverse_pointer
    zone_name = f"{reverse_zone.name}."

    if reverse_pointer.endswith(reverse_zone.name):
        return reverse_pointer[: -len(zone_name)]

    return f"{reverse_pointer}."


class RecordAutoPTRTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.zone_data = {
            "soa_mname": NameServer.objects.create(name="ns1.example.com"),
            "soa_rname": "hostmaster.example.com",
        }

        cls.zones = [
            Zone(name="zone1.example.com", **cls.zone_data),
            Zone(name="1.0.10.in-addr.arpa", **cls.zone_data),
            Zone(name="2.0.10.in-addr.arpa", **cls.zone_data),
            Zone(name="1.1.10.in-addr.arpa", **cls.zone_data),
            Zone(name="0.10.in-addr.arpa", **cls.zone_data),
            Zone(name="2.10.in-addr.arpa", **cls.zone_data),
            Zone(name="1.0.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **cls.zone_data),
            Zone(name="2.0.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **cls.zone_data),
            Zone(name="1.1.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **cls.zone_data),
            Zone(name="0.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **cls.zone_data),
            Zone(name="2.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **cls.zone_data),
            Zone(name="example.com", **cls.zone_data),
        ]
        for zone in cls.zones:
            zone.save()

    def test_create_ipv4_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_create_apex_ipv4_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "@"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{f_zone.name}.")

    def test_remove_ipv4_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        f_record.delete()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_create_multiple_ipv4(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        names = ["test1", "test2", "test3", "test4"]
        address = "10.0.1.42"

        for name in names:
            Record.objects.create(
                zone=f_zone,
                name=name,
                type=RecordTypeChoices.A,
                value=address,
            )

        r_records = Record.objects.filter(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )
        for r_record in r_records:
            self.assertTrue(
                r_record.value in [f"{name}.{f_zone.name}." for name in names]
            )

    def test_create_duplicate_ipv4_disable_ptr_1(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test2"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
            disable_ptr=True,
        )

        Record.objects.create(
            zone=f_zone,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name2}.{f_zone.name}.")

    def test_create_duplicate_ipv4_disable_ptr_2(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test2"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )

        Record.objects.create(
            zone=f_zone,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
            disable_ptr=True,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name1}.{f_zone.name}.")

    def test_change_name_ipv4(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test2"
        address = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )

        f_record.name = name2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name2}.{f_zone.name}.")

    def test_change_address_within_zone_ipv4(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address1 = "10.0.1.23"
        address2 = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_change_address_outside_zone_ipv4_old_zone(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address1 = "10.0.1.23"
        address2 = "10.0.2.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address1, r_zone),
            )

    def test_change_address_outside_zone_ipv4_new_zone(self):
        f_zone = self.zones[0]
        r_zone = self.zones[2]

        name = "test1"
        address1 = "10.0.1.23"
        address2 = "10.0.2.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_change_address_outside_zone_ipv4_no_zone(self):
        f_zone = self.zones[0]

        name = "test1"
        address1 = "10.0.1.23"
        address2 = "10.3.1.23"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR, value=f"{name}.{f_zone.name}."
            )

    def test_change_ttl_ipv4(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        f_record.ttl = 98765
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.ttl, 98765)

    def test_ipv4_delete_ptr_zone_with_parent(self):
        f_zone = self.zones[0]

        r_zone1 = self.zones[1]
        r_zone2 = self.zones[4]

        name = "test1"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_zone1.delete()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone2,
            name=reverse_name(address, r_zone2),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv4_create_ptr_zone_with_parent(self):
        f_zone = self.zones[0]

        name = "test1"
        address = "10.2.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_zone = Zone.objects.create(name="1.2.10.in-addr.arpa", **self.zone_data)

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv4_create_ptr_zone_without_parent(self):
        f_zone = self.zones[0]

        name = "test1"
        address = "10.3.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_zone = Zone.objects.create(name="1.3.10.in-addr.arpa", **self.zone_data)

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_create_ipv6_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_create_apex_ipv6_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "@"
        address = "fe80:dead:beef:1::42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{f_zone.name}.")

    def test_remove_ipv6_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        f_record.delete()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_create_multiple_ipv6(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        names = ["test1", "test2", "test3", "test4"]
        address = "fe80:dead:beef:1::42"

        for name in names:
            Record.objects.create(
                zone=f_zone,
                name=name,
                type=RecordTypeChoices.AAAA,
                value=address,
            )

        r_records = Record.objects.filter(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )
        for r_record in r_records:
            self.assertTrue(
                r_record.value in [f"{name}.{f_zone.name}." for name in names]
            )

    def test_create_duplicate_ipv6_disable_ptr_1(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test2"
        address = "fe80:dead:beef:1::42"

        Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
            disable_ptr=True,
        )

        Record.objects.create(
            zone=f_zone,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name2}.{f_zone.name}.")

    def test_create_duplicate_ipv6_disable_ptr_2(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test2"
        address = "fe80:dead:beef:1::42"

        Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        Record.objects.create(
            zone=f_zone,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
            disable_ptr=True,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name1}.{f_zone.name}.")

    def test_change_name_ipv6(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test2"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        f_record.name = name2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name2}.{f_zone.name}.")

    def test_change_address_within_zone_ipv6(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address1 = "fe80:dead:beef:1::23"
        address2 = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_change_address_outside_zone_ipv6_old_zone(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address1 = "fe80:dead:beef:1::23"
        address2 = "fe80:dead:beef:2::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address1, r_zone),
            )

    def test_change_address_outside_zone_ipv6_new_zone(self):
        f_zone = self.zones[0]
        r_zone = self.zones[7]

        name = "test1"
        address1 = "fe80:dead:beef:1::23"
        address2 = "fe80:dead:beef:2::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_change_address_outside_zone_ipv6_no_zone(self):
        f_zone = self.zones[0]

        name = "test1"
        address1 = "fe80:dead:beef:1::23"
        address2 = "fe80:dead:beef:31::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )

        f_record.value = address2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR, value=f"{name}.{f_zone.name}."
            )

    def test_change_ttl_ipv6(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        f_record.ttl = 98765
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.ttl, 98765)

    def test_ipv6_delete_ptr_zone_with_parent(self):
        f_zone = self.zones[0]

        r_zone1 = self.zones[6]
        r_zone2 = self.zones[9]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_zone1.delete()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone2,
            name=reverse_name(address, r_zone2),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv6_create_ptr_zone_with_parent(self):
        f_zone = self.zones[0]

        name = "test1"
        address = "fe80:dead:beef:21::42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_zone = Zone.objects.create(
            name="1.2.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **self.zone_data
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv6_create_ptr_zone_without_parent(self):
        f_zone = self.zones[0]

        name = "test1"
        address = "fe80:dead:beef:31::42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_zone = Zone.objects.create(
            name="1.3.0.0.f.e.e.b.d.a.e.d.0.8.e.f.ip6.arpa", **self.zone_data
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv4_remove_ptr_on_type_change(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name1 = "name1"
        name2 = "name2"
        address = "10.0.1.1"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )
        self.assertEqual(r_record.value, f"{name1}.{f_zone.name}.")

        f_record.type = RecordTypeChoices.CNAME
        f_record.value = name2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            r_record = Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_ipv6_remove_ptr_on_type_change(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name1 = "name1"
        name2 = "name2"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )
        self.assertEqual(r_record.value, f"{name1}.{f_zone.name}.")

        f_record.type = RecordTypeChoices.CNAME
        f_record.value = name2
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            r_record = Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_ipv4_create_inactive_record_no_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
            status=RecordStatusChoices.STATUS_INACTIVE,
        )

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_ipv4_deactivate_record_delete_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

        f_record.status = RecordStatusChoices.STATUS_INACTIVE
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_ipv4_activate_record_create_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[1]

        name = "test1"
        address = "10.0.1.42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.A,
            value=address,
            status=RecordStatusChoices.STATUS_INACTIVE,
        )

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

        f_record.status = RecordStatusChoices.STATUS_ACTIVE
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv6_create_inactive_record_no_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
            status=RecordStatusChoices.STATUS_INACTIVE,
        )

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

        f_record.status = RecordStatusChoices.STATUS_ACTIVE
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    def test_ipv6_deactivate_record_delete_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

        f_record.status = RecordStatusChoices.STATUS_INACTIVE
        f_record.save()

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    def test_ipv6_activate_record_create_ptr(self):
        f_zone = self.zones[0]
        r_zone = self.zones[6]

        name = "test1"
        address = "fe80:dead:beef:1::42"

        f_record = Record.objects.create(
            zone=f_zone,
            name=name,
            type=RecordTypeChoices.AAAA,
            value=address,
            status=RecordStatusChoices.STATUS_INACTIVE,
        )

        with self.assertRaises(Record.DoesNotExist):
            Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

        f_record.status = RecordStatusChoices.STATUS_ACTIVE
        f_record.save()

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.value, f"{name}.{f_zone.name}.")

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv4_multiple_address_records_one_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "10.0.1.42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertEqual(f_record1.ptr_record, r_record)
        self.assertEqual(f_record2.ptr_record, r_record)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv4_remove_address_record_from_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "10.0.1.42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

        f_record2.delete()

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv4_add_address_record_to_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "10.0.1.42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv4_remove_last_address_record_from_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "10.0.1.42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.A,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.A,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

        f_record2.delete()

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

        f_record1.delete()

        with self.assertRaises(Record.DoesNotExist):
            r_record = Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv4_use_existing_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[1]

        name1 = "test1"
        name2 = "test2"
        name3 = "test1.zone1"
        name4 = "test2.zone1"
        address1 = "10.0.1.42"
        address2 = "10.0.1.23"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.A,
            value=address1,
        )
        f_record2 = Record.objects.create(
            zone=f_zone1,
            name=name2,
            type=RecordTypeChoices.A,
            value=address2,
        )
        f_record3 = Record.objects.create(
            zone=f_zone2,
            name=name3,
            type=RecordTypeChoices.A,
            value=address1,
        )

        r_record1 = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address1, r_zone),
        )
        r_record2 = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record1.address_records.count(), 2)
        self.assertEqual(r_record2.address_records.count(), 1)
        self.assertIn(f_record1, r_record1.address_records.all())
        self.assertIn(f_record3, r_record1.address_records.all())
        self.assertIn(f_record2, r_record2.address_records.all())

        f_record3.name = name4
        f_record3.value = address2
        f_record3.save()

        self.assertEqual(r_record1.address_records.count(), 1)
        self.assertEqual(r_record2.address_records.count(), 2)
        self.assertIn(f_record1, r_record1.address_records.all())
        self.assertIn(f_record2, r_record2.address_records.all())
        self.assertIn(f_record3, r_record2.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv6_multiple_address_records_one_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "fe80:dead:beef:1::42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertEqual(f_record1.ptr_record, r_record)
        self.assertEqual(f_record2.ptr_record, r_record)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv6_remove_address_record_from_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "fe80:dead:beef:1::42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

        f_record2.delete()

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv6_add_address_record_to_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "fe80:dead:beef:1::42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv6_remove_last_address_record_from_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test1.zone1"
        address = "fe80:dead:beef:1::42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address,
        )
        f_record2 = Record.objects.create(
            zone=f_zone2,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address,
        )

        r_record = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address, r_zone),
        )

        self.assertEqual(r_record.address_records.count(), 2)
        self.assertIn(f_record1, r_record.address_records.all())
        self.assertIn(f_record2, r_record.address_records.all())

        f_record2.delete()

        self.assertEqual(r_record.address_records.count(), 1)
        self.assertIn(f_record1, r_record.address_records.all())

        f_record1.delete()

        with self.assertRaises(Record.DoesNotExist):
            r_record = Record.objects.get(
                type=RecordTypeChoices.PTR,
                zone=r_zone,
                name=reverse_name(address, r_zone),
            )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_ipv6_use_existing_ptr(self):
        f_zone1 = self.zones[0]
        f_zone2 = self.zones[11]
        r_zone = self.zones[6]

        name1 = "test1"
        name2 = "test2"
        name3 = "test1.zone1"
        name4 = "test2.zone1"
        address1 = "fe80:dead:beef:1::23"
        address2 = "fe80:dead:beef:1::42"

        f_record1 = Record.objects.create(
            zone=f_zone1,
            name=name1,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )
        f_record2 = Record.objects.create(
            zone=f_zone1,
            name=name2,
            type=RecordTypeChoices.AAAA,
            value=address2,
        )
        f_record3 = Record.objects.create(
            zone=f_zone2,
            name=name3,
            type=RecordTypeChoices.AAAA,
            value=address1,
        )

        r_record1 = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address1, r_zone),
        )
        r_record2 = Record.objects.get(
            type=RecordTypeChoices.PTR,
            zone=r_zone,
            name=reverse_name(address2, r_zone),
        )

        self.assertEqual(r_record1.address_records.count(), 2)
        self.assertEqual(r_record2.address_records.count(), 1)
        self.assertIn(f_record1, r_record1.address_records.all())
        self.assertIn(f_record3, r_record1.address_records.all())
        self.assertIn(f_record2, r_record2.address_records.all())

        f_record3.name = name4
        f_record3.value = address2
        f_record3.save()

        self.assertEqual(r_record1.address_records.count(), 1)
        self.assertEqual(r_record2.address_records.count(), 2)
        self.assertIn(f_record1, r_record1.address_records.all())
        self.assertIn(f_record2, r_record2.address_records.all())
        self.assertIn(f_record3, r_record2.address_records.all())
