from django.test import TestCase

from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import DNSSECKeyTemplate, DNSSECPolicy
from netbox_dns.filtersets import DNSSECKeyTemplateFilterSet
from netbox_dns.choices import (
    DNSSECKeyTemplateTypeChoices,
    DNSSECKeyTemplateAlgorithmChoices,
    DNSSECKeyTemplateKeySizeChoices,
)


class DNSSECKeyTemplateFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = DNSSECKeyTemplate.objects.all()
    filterset = DNSSECKeyTemplateFilterSet

    ignore_fields = ("policies",)

    @classmethod
    def setUpTestData(cls):
        cls.dnssec_key_templates = (
            DNSSECKeyTemplate(
                name="Test KSK",
                description="Test KSK",
                type=DNSSECKeyTemplateTypeChoices.TYPE_KSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
                lifetime=86400,
            ),
            DNSSECKeyTemplate(
                name="Test ZSK",
                description="Test ZSK",
                type=DNSSECKeyTemplateTypeChoices.TYPE_ZSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
                lifetime=86400,
                key_size=DNSSECKeyTemplateKeySizeChoices.SIZE_1024,
            ),
            DNSSECKeyTemplate(
                name="Test CSK",
                description="Test CSK",
                type=DNSSECKeyTemplateTypeChoices.TYPE_CSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.ED25519,
                lifetime=864000,
            ),
        )
        DNSSECKeyTemplate.objects.bulk_create(cls.dnssec_key_templates)

        cls.dnssec_policies = (
            DNSSECPolicy(name="Policy 1"),
            DNSSECPolicy(name="Policy 2"),
        )
        DNSSECPolicy.objects.bulk_create(cls.dnssec_policies)
        cls.dnssec_policies[0].key_templates.set(cls.dnssec_key_templates[0:2])
        cls.dnssec_policies[1].key_templates.set(cls.dnssec_key_templates[2:3])

    def test_name(self):
        params = {"name": ["Test KSK", "Test CSK"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_description(self):
        params = {"description__regex": r"Test [KC]SK"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_type(self):
        params = {"type": [DNSSECKeyTemplateTypeChoices.TYPE_CSK]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {
            "type": [
                DNSSECKeyTemplateTypeChoices.TYPE_KSK,
                DNSSECKeyTemplateTypeChoices.TYPE_ZSK,
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_algorithm(self):
        params = {"algorithm": [DNSSECKeyTemplateAlgorithmChoices.ED25519]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
        params = {
            "algorithm": [
                DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
                DNSSECKeyTemplateAlgorithmChoices.ED25519,
            ]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_lifetime(self):
        params = {"lifetime": 86400}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"lifetime": "P1D"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_key_size(self):
        params = {"key_size": [DNSSECKeyTemplateKeySizeChoices.SIZE_1024]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_policy(self):
        params = {"policy": [self.dnssec_policies[0].name]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)
        params = {"policy_id": [self.dnssec_policies[1].pk]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
