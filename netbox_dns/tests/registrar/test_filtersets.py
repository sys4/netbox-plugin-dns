from django.test import TestCase

from utilities.testing import ChangeLoggedFilterSetTests

from netbox_dns.models import Registrar
from netbox_dns.filtersets import RegistrarFilterSet


class RegistrarFilterSetTestCase(TestCase, ChangeLoggedFilterSetTests):
    queryset = Registrar.objects.all()
    filterset = RegistrarFilterSet

    @classmethod
    def setUpTestData(cls):
        cls.registrars = (
            Registrar(
                name="ACME 2 Corporation",
                description="Test Registrar 1",
                iana_id=4242,
                referral_url="https://acme.com",
                whois_server="whois.acme.com",
                address="42 Corp Street, Exampletown",
                abuse_email="abuse@acme.com",
                abuse_phone="+49.555.4242",
            ),
            Registrar(
                name="ACME 2 Limited",
                description="Test Registrar 2",
                iana_id=2323,
                referral_url="https://acme.com",
                whois_server="whois.acme.com",
                address="23 Limited Lane, Exampletown",
                abuse_email="abuse@acme.com",
                abuse_phone="+49.555.2323",
            ),
            Registrar(
                name="ACME 2 Trust",
                description="Test Registrar 3",
                iana_id=55,
                referral_url="https://acme.org",
                whois_server="whois.acme.org",
                address="55 Trust Street, Exampletown",
                abuse_email="abuse@acme.org",
                abuse_phone="+49.555.5555",
            ),
        )
        Registrar.objects.bulk_create(cls.registrars)

    def test_name(self):
        params = {"name": ["ACME 2 Corporation", "ACME 2 Trust"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_description(self):
        params = {"description": ["Test Registrar 1", "Test Registrar 3"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_iana_id(self):
        params = {"iana_id": [2323, 4242, 1234]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_referral_url(self):
        params = {"referral_url": ["https://acme.org"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_whois_server(self):
        params = {"whois_server": ["whois.acme.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 2)

    def test_address(self):
        params = {
            "address": ["23 Limited Lane, Exampletown", "007 Bond Street, Exampletown"]
        }
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_abuse_email(self):
        params = {"abuse_email": ["abuse@acme.org", "abuse@acme.com"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 3)

    def test_abuse_phone(self):
        params = {"abuse_phone": ["+49.555.5555", "+49.555.1111"]}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)
