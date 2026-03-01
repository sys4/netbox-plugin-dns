from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from utilities.testing import ViewTestCases, create_tags

from netbox_dns.tests.custom import ModelViewTestCase
from netbox_dns.models import View, Zone, NameServer, Record
from netbox_dns.choices import RecordTypeChoices, RecordStatusChoices, ZoneStatusChoices


class RecordViewTestCase(
    ModelViewTestCase,
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.CreateObjectViewTestCase,
    ViewTestCases.EditObjectViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.BulkImportObjectsViewTestCase,
    ViewTestCases.BulkEditObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    model = Record

    @classmethod
    def setUpTestData(cls):
        cls.zone_data = {
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
            Zone(name="zone1.example.com", **cls.zone_data, view=default_view),
            Zone(name="zone2.example.com", **cls.zone_data, view=default_view),
            Zone(name="zone1.example.com", **cls.zone_data, view=views[0]),
            Zone(name="zone2.example.com", **cls.zone_data, view=views[0]),
            Zone(name="zone1.example.com", **cls.zone_data, view=views[1]),
            Zone(name="zone2.example.com", **cls.zone_data, view=views[1]),
            Zone(name="zone3.example.com", **cls.zone_data, view=views[1]),
        )
        Zone.objects.bulk_create(cls.zones)

        cls.records = (
            Record(
                zone=cls.zones[0],
                type=RecordTypeChoices.CNAME,
                name="name1",
                value="test1.example.com.",
                ttl=100,
            ),
            Record(
                zone=cls.zones[1],
                type=RecordTypeChoices.A,
                name="name2",
                value="192.168.1.1",
                ttl=200,
            ),
            Record(
                zone=cls.zones[0],
                type=RecordTypeChoices.AAAA,
                name="name2",
                value="fe80:dead:beef::42",
                ttl=86400,
            ),
            Record(
                zone=cls.zones[4],
                type=RecordTypeChoices.TXT,
                name="@",
                value="Test Text",
                ttl=86400,
            ),
            Record(
                zone=cls.zones[2],
                type=RecordTypeChoices.AAAA,
                name="name42",
                value="fe80:dead:beef::42",
                ttl=86400,
            ),
        )
        for record in cls.records:
            record.save()

        tags = create_tags("Alpha", "Bravo", "Charlie")

        cls.form_data = {
            "zone": cls.zones[0].pk,
            "type": RecordTypeChoices.AAAA,
            "name": "name3",
            "value": "fe80::dead:beef",
            "ttl": 86230,
            "tags": [t.pk for t in tags],
            "status": RecordStatusChoices.STATUS_ACTIVE,
        }

        cls.bulk_edit_data = {
            "zone": cls.zones[1].pk,
            "type": RecordTypeChoices.TXT,
            "value": "Test",
            "status": RecordStatusChoices.STATUS_INACTIVE,
            "ttl": 86420,
            "disable_ptr": False,
            "description": "New Description",
        }

        cls.csv_data = (
            "zone,view,type,name,value,ttl",
            "zone1.example.com,,A,@,10.10.10.10,3600",
            "zone2.example.com,,AAAA,name4,fe80::dead:beef,7200",
            "zone1.example.com,,CNAME,dns,name1.zone2.example.com,100",
            "zone2.example.com,,TXT,textname,textvalue,1000",
            "zone1.example.com,view1,A,@,10.10.10.10,3600",
            "zone2.example.com,view1,AAAA,name4,fe80::dead:beef,7200",
            "zone1.example.com,view1,CNAME,dns,name1.zone2.example.com,100",
            "zone2.example.com,view1,TXT,textname,textvalue,1000",
            "zone1.example.com,view2,A,@,10.10.10.10,3600",
            "zone2.example.com,view2,AAAA,name4,fe80::dead:beef,7200",
            "zone1.example.com,view2,CNAME,dns,name1.zone2.example.com,100",
            "zone2.example.com,view2,TXT,textname,textvalue,1000",
        )

        cls.csv_update_data = (
            "id,zone,type,value,ttl",
            f"{cls.records[0].pk},{cls.zones[0].name},{RecordTypeChoices.A},10.0.1.1,86442",
            f"{cls.records[1].pk},{cls.zones[1].name},{RecordTypeChoices.AAAA},fe80:dead:beef::23,86423",
        )

    maxDiff = None

    def test_warning_cname_target_ok_target_present(self):
        self.add_permissions("netbox_dns.view_record")

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name1.zone1.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    def test_warning_cname_warn_target_missing(self):
        self.add_permissions("netbox_dns.view_record")

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name42.zone1.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    def test_warning_cname_warn_different_view(self):
        self.add_permissions("netbox_dns.view_record")

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name42.zone1.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    def test_warning_cname_target_ok_no_zone(self):
        self.add_permissions("netbox_dns.view_record")

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name42.zone42.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    def test_warning_cname_target_ok_inactive_zone(self):
        self.add_permissions("netbox_dns.view_record")

        self.zones[0].status = ZoneStatusChoices.STATUS_RESERVED
        self.zones[0].save()

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name42.zone1.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    def test_warning_cname_target_ok_different_view(self):
        self.add_permissions("netbox_dns.view_record")

        record = Record.objects.create(
            name="test1",
            zone=self.zones[1],
            type=RecordTypeChoices.CNAME,
            value="name42.zone3.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "There is no matching target record for CNAME value",
        )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_warning_mask_record(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="fe80:dead:beef::42",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    def test_warning_mask_record_different_view_ok(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="zone3",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="fe80:dead:beef::42",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    def test_warning_mask_record_ns_ok(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.NS,
            value="ns1.zone1.example.com.",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    def test_warning_mask_record_ds_ok(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.DS,
            value="12391 8 2 3CC08159BADEADBEEFA6A74203F8019462384490BA47119918994315 EEA6DEB2",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    def test_warning_mask_record_glue_a_ok(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)

        self.zones[0].nameservers.set(
            (NameServer.objects.create(name="ns1.zone1.example.com"),)
        )

        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.NS,
            value="ns1.zone1.example.com.",
        )
        record = Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="10.0.0.42",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_warning_mask_record_nonglue_a_warn(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.A,
            value="10.0.0.42",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    def test_warning_mask_record_glue_aaaa_ok(self):
        self.add_permissions("netbox_dns.view_record")

        self.zones[0].nameservers.set(
            (NameServer.objects.create(name="ns1.zone1.example.com"),)
        )

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        Record.objects.create(
            name="zone1",
            zone=zone,
            type=RecordTypeChoices.NS,
            value="ns1.zone1.example.com.",
        )
        record = Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="fe80::dead:beef",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertNotRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_dns": {
                "enforce_zone_cut_checking": False,
            }
        }
    )
    def test_warning_mask_record_nonglue_aaaa_warn(self):
        self.add_permissions("netbox_dns.view_record")

        zone = Zone.objects.create(name="example.com", **self.zone_data)
        record = Record.objects.create(
            name="ns1.zone1",
            zone=zone,
            type=RecordTypeChoices.AAAA,
            value="fe80::dead:beef",
        )

        url = reverse("plugins:netbox_dns:record", kwargs={"pk": record.pk})

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        self.assertRegex(
            response.content.decode(),
            "Record is masked by a child zone and may not be visible in DNS",
        )
