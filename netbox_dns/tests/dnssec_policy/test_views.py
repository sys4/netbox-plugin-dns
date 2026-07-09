from django.urls import reverse
from rest_framework import status

from netbox_dns.choices import (
    DNSSECKeyTemplateAlgorithmChoices,
    DNSSECKeyTemplateTypeChoices,
    DNSSECPolicyDigestChoices,
    DNSSECPolicyStatusChoices,
)
from netbox_dns.models import (
    DNSSECKeyTemplate,
    DNSSECPolicy,
    NameServer,
    Zone,
    ZoneTemplate,
)
from netbox_dns.tests.custom import ModelViewTestCase
from utilities.testing import ViewTestCases, create_tags, post_data


class DNSSECPolicyViewTestCase(
    ModelViewTestCase,
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.CreateObjectViewTestCase,
    ViewTestCases.EditObjectViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.BulkImportObjectsViewTestCase,
    ViewTestCases.BulkEditObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    model = DNSSECPolicy

    @classmethod
    def setUpTestData(cls):
        cls.dnssec_key_templates = (
            DNSSECKeyTemplate(
                name="csk-template1",
                type=DNSSECKeyTemplateTypeChoices.TYPE_CSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
            ),
            DNSSECKeyTemplate(
                name="csk-template2",
                type=DNSSECKeyTemplateTypeChoices.TYPE_CSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.ED25519,
            ),
            DNSSECKeyTemplate(
                name="ksk-template1",
                type=DNSSECKeyTemplateTypeChoices.TYPE_KSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
            ),
            DNSSECKeyTemplate(
                name="ksk-template2",
                type=DNSSECKeyTemplateTypeChoices.TYPE_KSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.ED25519,
            ),
            DNSSECKeyTemplate(
                name="zsk-template1",
                type=DNSSECKeyTemplateTypeChoices.TYPE_ZSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
            ),
            DNSSECKeyTemplate(
                name="zsk-template2",
                type=DNSSECKeyTemplateTypeChoices.TYPE_ZSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.ED25519,
            ),
        )
        DNSSECKeyTemplate.objects.bulk_create(cls.dnssec_key_templates)

        cls.dnssec_policies = (
            DNSSECPolicy(
                name="Test Policy 4",
                inline_signing=True,
                status=DNSSECPolicyStatusChoices.STATUS_ACTIVE,
                dnskey_ttl=3600,
                purge_keys=7776000,
                publish_safety=3600,
                retire_safety=3600,
                signatures_jitter=43200,
                signatures_refresh=432000,
                signatures_validity=1209600,
                signatures_validity_dnskey=1209600,
                max_zone_ttl=86400,
                zone_propagation_delay=300,
                create_cdnskey=True,
                cds_digest_types=[DNSSECPolicyDigestChoices.SHA256],
                parent_ds_ttl=86400,
                parent_propagation_delay=3600,
                use_nsec3=True,
                nsec3_iterations=None,
                nsec3_opt_out=False,
                nsec3_salt_size=None,
            ),
            DNSSECPolicy(
                name="Test Policy 5",
                inline_signing=True,
            ),
            DNSSECPolicy(
                name="Test Policy 6",
                inline_signing=False,
                max_zone_ttl=43200,
                create_cdnskey=True,
                use_nsec3=False,
            ),
        )
        DNSSECPolicy.objects.bulk_create(cls.dnssec_policies)

        tags = create_tags("Alpha", "Bravo", "Charlie")

        cls.form_data = {
            "name": "Test Policy 1",
            "inline_signing": True,
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "dnskey_ttl": 3600,
            "purge_keys": 7776000,
            "publish_safety": 3600,
            "retire_safety": 3600,
            "signatures_jitter": 43200,
            "signatures_refresh": 432000,
            "signatures_validity": 1209600,
            "signatures_validity_dnskey": 1209600,
            "max_zone_ttl": 86400,
            "zone_propagation_delay": 300,
            "create_cdnskey": True,
            "cds_digest_types": [DNSSECPolicyDigestChoices.SHA256],
            "parent_ds_ttl": 86400,
            "parent_propagation_delay": 3600,
            "use_nsec3": True,
            "nsec3_iterations": None,
            "nsec3_opt_out": False,
            "nsec3_salt_size": None,
            "tags": [t.pk for t in tags],
        }

        cls.bulk_edit_data = {
            "description": "Update Description",
            "inline_signing": False,
            "status": DNSSECPolicyStatusChoices.STATUS_INACTIVE,
            "dnskey_ttl": 7200,
            "purge_keys": 7776999,
            "publish_safety": 7200,
            "retire_safety": 7200,
            "signatures_jitter": 43299,
            "signatures_refresh": 432999,
            "signatures_validity": 1209699,
            "signatures_validity_dnskey": 1209699,
            "max_zone_ttl": 86499,
            "zone_propagation_delay": 600,
            "create_cdnskey": False,
            "cds_digest_types": [DNSSECPolicyDigestChoices.SHA384],
            "parent_ds_ttl": 86499,
            "parent_propagation_delay": 7200,
            "use_nsec3": False,
            "nsec3_iterations": 1,
            "nsec3_opt_out": True,
            "nsec3_salt_size": 32,
        }

        cls.csv_data = (
            "name,status,dnskey_ttl,max_zone_ttl,create_cdnskey,use_nsec3,inline_signing",
            f"Test Policy 1,{DNSSECPolicyStatusChoices.STATUS_ACTIVE},86400,43200,true,true,false",
            "Test Policy 2,,86400,43200,false,true,true",
            f"Test Policy 3,{DNSSECPolicyStatusChoices.STATUS_INACTIVE},43200,86400,true,false,true",
        )

        cls.csv_update_data = (
            "id,description,use_nsec3,create_cdnskey,inline_signing",
            f"{cls.dnssec_policies[0].pk},Test Description 1,true,true,true",
            f"{cls.dnssec_policies[1].pk},Test Description 2,false,false,true",
        )

    maxDiff = None

    def test_ksk_zsk(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[2]
        key_template2 = self.dnssec_key_templates[4]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()

        self.assertIn(key_template1, policy.key_templates.all())
        self.assertIn(key_template2, policy.key_templates.all())
        self.assertEqual(policy.max_zone_ttl, 424242)

    def test_csk(self):
        policy = self.dnssec_policies[0]

        key_template = self.dnssec_key_templates[0]

        policy = self.dnssec_policies[0]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()

        self.assertIn(key_template, policy.key_templates.all())
        self.assertEqual(policy.max_zone_ttl, 424242)

    def test_csk_ksk_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[0]
        key_template2 = self.dnssec_key_templates[2]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_csk_zsk_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[0]
        key_template2 = self.dnssec_key_templates[4]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_csk_csk_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[0]
        key_template2 = self.dnssec_key_templates[1]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_ksk_ksk_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[2]
        key_template2 = self.dnssec_key_templates[3]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_zsk_zsk_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[4]
        key_template2 = self.dnssec_key_templates[5]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_ksk_zsk_different_algorithm_fail(self):
        policy = self.dnssec_policies[0]

        key_template1 = self.dnssec_key_templates[2]
        key_template2 = self.dnssec_key_templates[5]

        self.add_permissions(
            "netbox_dns.change_dnssecpolicy",
            "netbox_dns.view_dnsseckeytemplate",
        )

        request_data = {
            "name": policy.name,
            "key_templates": [
                key_template1.pk,
                key_template2.pk,
            ],
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": 424242,
        }
        request = {
            "path": self._get_url("edit", instance=policy),
            "data": post_data(request_data),
        }

        response = self.client.post(**request)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        policy.refresh_from_db()

        self.assertFalse(policy.key_templates.exists())
        self.assertEqual(policy.max_zone_ttl, 86400)

    def test_create_iso8601_dnskey_ttl(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "dnskey_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.dnskey_ttl, 42 * 86400)

    def test_update_iso8601_dnskey_ttl(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "dnskey_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.dnskey_ttl, 42 * 86400)

    def test_create_iso8601_purge_keys(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "purge_keys": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.purge_keys, 42 * 86400)

    def test_update_iso8601_purge_keys(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "purge_keys": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.purge_keys, 42 * 86400)

    def test_create_iso8601_publish_safety(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "publish_safety": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.publish_safety, 42 * 86400)

    def test_update_iso8601_publish_safety(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "publish_safety": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.publish_safety, 42 * 86400)

    def test_create_iso8601_retire_safety(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "retire_safety": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.retire_safety, 42 * 86400)

    def test_update_iso8601_retire_safety(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "retire_safety": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.retire_safety, 42 * 86400)

    def test_create_iso8601_signatures_jitter(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "signatures_jitter": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.signatures_jitter, 42 * 86400)

    def test_update_iso8601_signatures_jitter(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "signatures_jitter": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.signatures_jitter, 42 * 86400)

    def test_create_iso8601_signatures_refresh(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "signatures_refresh": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.signatures_refresh, 42 * 86400)

    def test_update_iso8601_signatures_refresh(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "signatures_refresh": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.signatures_refresh, 42 * 86400)

    def test_create_iso8601_signatures_validity(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "signatures_validity": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.signatures_validity, 42 * 86400)

    def test_update_iso8601_signatures_validity(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "signatures_validity": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.signatures_validity, 42 * 86400)

    def test_create_iso8601_signatures_validity_dnskey(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "signatures_validity_dnskey": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.signatures_validity_dnskey, 42 * 86400)

    def test_update_iso8601_signatures_validity_dnskey(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "signatures_validity_dnskey": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.signatures_validity_dnskey, 42 * 86400)

    def test_create_iso8601_max_zone_ttl(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "max_zone_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.max_zone_ttl, 42 * 86400)

    def test_update_iso8601_max_zone_ttl(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "max_zone_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.max_zone_ttl, 42 * 86400)

    def test_create_iso8601_zone_propagation_delay(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "zone_propagation_delay": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.zone_propagation_delay, 42 * 86400)

    def test_update_iso8601_zone_propagation_delay(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "zone_propagation_delay": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.zone_propagation_delay, 42 * 86400)

    def test_create_iso8601_parent_ds_ttl(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "parent_ds_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.parent_ds_ttl, 42 * 86400)

    def test_update_iso8601_parent_ds_ttl(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "parent_ds_ttl": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.parent_ds_ttl, 42 * 86400)

    def test_create_iso8601_parent_propagation_delay(self):
        self.add_permissions("netbox_dns.add_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_add")

        request_data = {
            "name": "Test Policy 7",
            "status": DNSSECPolicyStatusChoices.STATUS_ACTIVE,
            "parent_propagation_delay": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy = DNSSECPolicy.objects.get(name="Test Policy 7")
        self.assertEqual(policy.status, DNSSECPolicyStatusChoices.STATUS_ACTIVE)
        self.assertEqual(policy.parent_propagation_delay, 42 * 86400)

    def test_update_iso8601_parent_propagation_delay(self):
        policy = self.dnssec_policies[0]

        self.add_permissions("netbox_dns.change_dnssecpolicy")

        url = reverse("plugins:netbox_dns:dnssecpolicy_edit", kwargs={"pk": policy.pk})
        request_data = {
            "name": policy.name,
            "status": policy.status,
            "parent_propagation_delay": "P42D",
        }
        request = {
            "data": post_data(request_data),
        }

        response = self.client.get(path=url)
        self.assertHttpStatus(response, status.HTTP_200_OK)

        response = self.client.post(path=url, **request)
        self.assertHttpStatus(response, status.HTTP_302_FOUND)

        policy.refresh_from_db()
        self.assertEqual(policy.parent_propagation_delay, 42 * 86400)

    def test_zones_viewtab(self):
        policy = self.dnssec_policies[0]

        nameserver = NameServer.objects.create(name="ns1.example.com")
        Zone.objects.create(
            name="zone1.example.com",
            soa_mname=nameserver,
            soa_rname="hostmaster.example.com",
            dnssec_policy=policy,
        )

        self.add_permissions(
            "netbox_dns.view_dnssecpolicy",
        )

        request = {
            "path": self._get_url("zones", instance=policy),
        }

        response = self.client.get(**request)
        self.assertHttpStatus(response, 200)

    def test_zonetemplates_viewtab(self):
        policy = self.dnssec_policies[0]

        ZoneTemplate.objects.create(
            name="Test Zone Template 1",
            dnssec_policy=policy,
        )

        self.add_permissions(
            "netbox_dns.view_dnssecpolicy",
        )

        request = {
            "path": self._get_url("zonetemplates", instance=policy),
        }

        response = self.client.get(**request)
        self.assertHttpStatus(response, 200)
