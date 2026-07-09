"""
End-to-end branching integration tests for NetBox DNS.

Each test provisions a real NetBox Branching branch, makes DNS changes inside
it, and merges / reverts the branch — asserting that the changes appear in (and
disappear from) the main schema at the right times.

The interesting cases are the many-to-many relations: ``Zone.nameservers``,
``View.prefixes``, ``ZoneTemplate.nameservers`` / ``record_templates`` and
``DNSSECPolicy.key_templates``.  Their auto-generated through models are plain
``models.Model`` subclasses; without the resolver registered in
``netbox_dns.branching`` their rows would be routed to the main schema even
inside a branch and the branch would fail to merge cleanly.  Assigning
nameservers to a zone additionally drives ``Zone.update_ns_records()``, which
reads the zone's own nameservers and NS records back out through those
relations — the exact path the original bug reports pointed at.
"""

import unittest

from django.test import TestCase

from netbox_dns.branching import (
    _m2m_through_models,
    supports_branching_resolver,
)
from netbox_dns.choices import (
    DNSSECKeyTemplateAlgorithmChoices,
    DNSSECKeyTemplateTypeChoices,
    RecordTypeChoices,
)
from netbox_dns.models import (
    DNSSECKeyTemplate,
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

from .base import (
    HAS_BRANCHING,
    BranchingTestBase,
    TestBase,
    make_request,
    provision_branch,
)

if HAS_BRANCHING:
    from netbox_branching.choices import (
        BranchMergeStrategyChoices,
        BranchStatusChoices,
    )
    from netbox_branching.utilities import activate_branch

    from netbox.context_managers import event_tracking


ZONE_DEFAULTS = {
    "soa_rname": "hostmaster.example.com",
}


# ── Resolver unit tests (no branch provisioning required) ────────────────────


class BranchingResolverTestCase(TestCase):
    """
    Fast unit tests for the resolver itself; these don't need a provisioned
    branch, so they run even without netbox-branching installed.
    """

    def test_primary_models_are_branchable(self):
        for model in (
            NameServer,
            Zone,
            Record,
            View,
            ZoneTemplate,
            RecordTemplate,
            DNSSECPolicy,
            DNSSECKeyTemplate,
        ):
            with self.subTest(model=model.__name__):
                self.assertIs(supports_branching_resolver(model), True)

    def test_m2m_through_models_are_branchable(self):
        through_models = _m2m_through_models()

        # Sanity check: every declared DNS m2m field is represented.
        self.assertIn(Zone.nameservers.through, through_models)
        self.assertIn(View.prefixes.through, through_models)
        self.assertIn(ZoneTemplate.nameservers.through, through_models)
        self.assertIn(ZoneTemplate.record_templates.through, through_models)
        self.assertIn(DNSSECPolicy.key_templates.through, through_models)

        for through in through_models:
            with self.subTest(model=through.__name__):
                self.assertIs(supports_branching_resolver(through), True)

    def test_foreign_models_defer(self):
        # Models outside netbox_dns — including the ipam.Prefix m2m target —
        # must defer (return None) rather than being claimed by this resolver.
        from ipam.models import Prefix
        from tenancy.models import Tenant

        for model in (Prefix, Tenant):
            with self.subTest(model=model.__name__):
                self.assertIsNone(supports_branching_resolver(model))


# ── Shared merge / revert tests (run against every merge strategy) ───────────


@unittest.skipUnless(HAS_BRANCHING, "netbox-branching is not installed")
class BaseBranchingTests(BranchingTestBase):
    """
    Merge and revert tests that run against every merge strategy.

    Concrete subclasses set ``MERGE_STRATEGY`` and also inherit from
    ``TestBase`` (``TransactionTestCase``).
    """

    MERGE_STRATEGY = None

    def _merge(self, branch):
        branch.merge(user=self.user, commit=True)
        branch.refresh_from_db()
        self.assertEqual(branch.status, BranchStatusChoices.MERGED)

    def _revert(self, branch):
        branch.revert(user=self.user, commit=True)
        branch.refresh_from_db()

    # ── basic object lifecycle ───────────────────────────────────────────────

    def test_simple_merge_and_revert(self):
        """A NameServer + Zone created in a branch round-trips through main."""
        branch = provision_branch("Simple", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            nameserver = NameServer.objects.create(name="ns1.example.com")
            zone = Zone.objects.create(
                name="zone1.example.com", soa_mname=nameserver, **ZONE_DEFAULTS
            )

        ns_pk, zone_pk = nameserver.pk, zone.pk

        # Nothing visible in main before the merge.
        self.assertFalse(NameServer.objects.filter(pk=ns_pk).exists())
        self.assertFalse(Zone.objects.filter(pk=zone_pk).exists())

        self._merge(branch)

        self.assertTrue(NameServer.objects.filter(pk=ns_pk).exists())
        zone_main = Zone.objects.get(pk=zone_pk)
        self.assertEqual(zone_main.name, "zone1.example.com")
        # The managed SOA record created on zone save came along too.
        self.assertTrue(
            zone_main.records.filter(type=RecordTypeChoices.SOA, managed=True).exists()
        )

        self._revert(branch)

        self.assertFalse(NameServer.objects.filter(pk=ns_pk).exists())
        self.assertFalse(Zone.objects.filter(pk=zone_pk).exists())

    # ── everything at once ───────────────────────────────────────────────────

    def test_comprehensive_merge_and_revert(self):
        """
        Create one object of every NetBox DNS model type inside a branch,
        wired together through their FK and m2m relations, then merge and
        revert — asserting the whole graph appears in main on merge and
        disappears again on revert.
        """
        branch = provision_branch("Comprehensive", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            view = View.objects.create(name="internal")
            ns1 = NameServer.objects.create(name="ns1.example.com")
            ns2 = NameServer.objects.create(name="ns2.example.com")
            registrar = Registrar.objects.create(name="ACME Registrar", iana_id=4242)
            registrant = RegistrationContact.objects.create(
                contact_id="REG-1", name="Registrant"
            )
            admin_c = RegistrationContact.objects.create(
                contact_id="ADM-1", name="Admin"
            )

            key_template = DNSSECKeyTemplate.objects.create(
                name="CSK",
                type=DNSSECKeyTemplateTypeChoices.TYPE_CSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
                lifetime=86400,
            )
            policy = DNSSECPolicy.objects.create(name="Default policy")
            policy.key_templates.add(key_template)

            record_template = RecordTemplate.objects.create(
                name="www template",
                record_name="www",
                type=RecordTypeChoices.A,
                value="10.0.0.1",
            )
            zone_template = ZoneTemplate.objects.create(name="Standard")
            zone_template.nameservers.add(ns1)
            zone_template.record_templates.add(record_template)

            zone = Zone.objects.create(
                name="example.com",
                view=view,
                soa_mname=ns1,
                registrar=registrar,
                registrant=registrant,
                admin_c=admin_c,
                **ZONE_DEFAULTS,
            )
            zone.nameservers.set([ns1, ns2])
            record = Record.objects.create(
                zone=zone,
                name="www",
                type=RecordTypeChoices.A,
                value="10.0.0.1",
            )

        pks = {
            View: view.pk,
            NameServer: ns1.pk,
            Registrar: registrar.pk,
            RegistrationContact: registrant.pk,
            DNSSECKeyTemplate: key_template.pk,
            DNSSECPolicy: policy.pk,
            RecordTemplate: record_template.pk,
            ZoneTemplate: zone_template.pk,
            Zone: zone.pk,
            Record: record.pk,
        }

        # Before merge: none of it exists in main.
        for model, pk in pks.items():
            self.assertFalse(
                model.objects.filter(pk=pk).exists(),
                f"{model.__name__} must not be in main before merge",
            )

        self._merge(branch)

        # After merge: everything exists in main, with relations intact.
        for model, pk in pks.items():
            self.assertTrue(
                model.objects.filter(pk=pk).exists(),
                f"{model.__name__} must be in main after merge",
            )

        zone_main = Zone.objects.get(pk=zone.pk)
        self.assertEqual(zone_main.view_id, view.pk)
        self.assertEqual(zone_main.soa_mname_id, ns1.pk)
        self.assertEqual(zone_main.registrar_id, registrar.pk)
        self.assertEqual(zone_main.registrant_id, registrant.pk)
        self.assertEqual(zone_main.admin_c_id, admin_c.pk)
        self.assertEqual(
            set(zone_main.nameservers.values_list("name", flat=True)),
            {"ns1.example.com", "ns2.example.com"},
        )
        self.assertEqual(
            list(
                DNSSECPolicy.objects.get(pk=policy.pk).key_templates.values_list(
                    "name", flat=True
                )
            ),
            ["CSK"],
        )
        zt_main = ZoneTemplate.objects.get(pk=zone_template.pk)
        self.assertEqual(
            list(zt_main.nameservers.values_list("name", flat=True)),
            ["ns1.example.com"],
        )
        self.assertEqual(
            list(zt_main.record_templates.values_list("name", flat=True)),
            ["www template"],
        )
        # The user-created A record plus the managed SOA/NS records all merged.
        self.assertEqual(Record.objects.get(pk=record.pk).value, "10.0.0.1")
        self.assertTrue(
            zone_main.records.filter(type=RecordTypeChoices.SOA, managed=True).exists()
        )
        self.assertEqual(
            set(
                zone_main.records.filter(
                    type=RecordTypeChoices.NS, managed=True, name="@"
                ).values_list("value", flat=True)
            ),
            {"ns1.example.com.", "ns2.example.com."},
        )

        self._revert(branch)

        # After revert: the whole graph is gone from main again.
        for model, pk in pks.items():
            self.assertFalse(
                model.objects.filter(pk=pk).exists(),
                f"{model.__name__} must be gone from main after revert",
            )

    # ── the core m2m case: Zone.nameservers ──────────────────────────────────

    def test_zone_nameservers_m2m_merge_and_revert(self):
        """
        Assigning nameservers to a zone inside a branch must merge cleanly.

        This drives the ``Zone.nameservers`` m2m through model *and*
        ``Zone.update_ns_records()`` (via the ``m2m_changed`` receiver), which
        reads the zone's own nameservers/NS records — the path that previously
        broke because the through model wasn't branch-aware.
        """
        branch = provision_branch("NS m2m", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            ns1 = NameServer.objects.create(name="ns1.example.com")
            ns2 = NameServer.objects.create(name="ns2.example.com")
            zone = Zone.objects.create(
                name="example.com", soa_mname=ns1, **ZONE_DEFAULTS
            )
            zone.nameservers.set([ns1, ns2])

            # The managed NS records must exist inside the branch.
            branch_ns_values = set(
                zone.records.filter(
                    type=RecordTypeChoices.NS, managed=True, name="@"
                ).values_list("value", flat=True)
            )
            self.assertEqual(branch_ns_values, {"ns1.example.com.", "ns2.example.com."})

        zone_pk = zone.pk

        # The m2m assignment must not have leaked into main before the merge.
        self.assertFalse(Zone.objects.filter(pk=zone_pk).exists())

        self._merge(branch)

        zone_main = Zone.objects.get(pk=zone_pk)
        self.assertEqual(
            set(zone_main.nameservers.values_list("name", flat=True)),
            {"ns1.example.com", "ns2.example.com"},
        )
        ns_values = set(
            zone_main.records.filter(
                type=RecordTypeChoices.NS, managed=True, name="@"
            ).values_list("value", flat=True)
        )
        self.assertEqual(ns_values, {"ns1.example.com.", "ns2.example.com."})

        self._revert(branch)

        self.assertFalse(Zone.objects.filter(pk=zone_pk).exists())

    def test_zone_nameserver_removal_merge_and_revert(self):
        """
        Removing a nameserver from an existing zone inside a branch merges.

        Mirrors the reported failure mode (deleting objects that have
        associated DNS records inside a branch, then merging).  The removal
        fires ``update_ns_records()`` which deletes the managed NS record.
        """
        # Seed the zone with two nameservers in main first.
        ns1 = NameServer.objects.create(name="ns1.example.com")
        ns2 = NameServer.objects.create(name="ns2.example.com")
        zone = Zone.objects.create(name="example.com", soa_mname=ns1, **ZONE_DEFAULTS)
        zone.nameservers.set([ns1, ns2])
        zone_pk = zone.pk

        branch = provision_branch("NS removal", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            branch_zone = Zone.objects.get(pk=zone_pk)
            # Snapshot before mutating so the ObjectChange records prechange
            # data — needed for the revert path to reconstruct the prior state.
            branch_zone.snapshot()
            branch_zone.nameservers.remove(ns2)

        # Main still has both until the merge.
        self.assertEqual(Zone.objects.get(pk=zone_pk).nameservers.count(), 2)

        self._merge(branch)

        zone_main = Zone.objects.get(pk=zone_pk)
        self.assertEqual(
            set(zone_main.nameservers.values_list("name", flat=True)),
            {"ns1.example.com"},
        )
        ns_values = set(
            zone_main.records.filter(
                type=RecordTypeChoices.NS, managed=True, name="@"
            ).values_list("value", flat=True)
        )
        self.assertEqual(ns_values, {"ns1.example.com."})

        self._revert(branch)

        self.assertEqual(
            set(
                Zone.objects.get(pk=zone_pk).nameservers.values_list("name", flat=True)
            ),
            {"ns1.example.com", "ns2.example.com"},
        )

    # ── unmanaged records created inside a branch ────────────────────────────

    def test_records_created_in_branch_merge_and_revert(self):
        """Plain A records added to an existing zone inside a branch round-trip."""
        nameserver = NameServer.objects.create(name="ns1.example.com")
        zone = Zone.objects.create(
            name="example.com", soa_mname=nameserver, **ZONE_DEFAULTS
        )
        zone.nameservers.add(nameserver)
        zone_pk = zone.pk

        branch = provision_branch("Records", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            branch_zone = Zone.objects.get(pk=zone_pk)
            record = Record.objects.create(
                zone=branch_zone,
                name="www",
                type=RecordTypeChoices.A,
                value="10.0.0.1",
            )

        record_pk = record.pk
        self.assertFalse(Record.objects.filter(pk=record_pk).exists())

        self._merge(branch)

        record_main = Record.objects.get(pk=record_pk)
        self.assertEqual(record_main.value, "10.0.0.1")
        self.assertEqual(record_main.zone_id, zone_pk)

        self._revert(branch)

        self.assertFalse(Record.objects.filter(pk=record_pk).exists())

    # ── View.prefixes m2m (cross-app target: ipam.Prefix) ────────────────────

    def test_view_prefixes_m2m_merge_and_revert(self):
        """
        ``View.prefixes`` points at ``ipam.Prefix`` (a different app).  The
        through model still belongs to netbox_dns and must be branch-aware.
        """
        from ipam.models import Prefix

        prefix = Prefix.objects.create(prefix="10.0.0.0/24")
        prefix_pk = prefix.pk

        branch = provision_branch("View prefixes", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            view = View.objects.create(name="internal")
            branch_prefix = Prefix.objects.get(pk=prefix_pk)
            view.prefixes.add(branch_prefix)

        view_pk = view.pk
        self.assertFalse(View.objects.filter(pk=view_pk).exists())

        self._merge(branch)

        view_main = View.objects.get(pk=view_pk)
        self.assertEqual(
            list(view_main.prefixes.values_list("pk", flat=True)), [prefix_pk]
        )

        self._revert(branch)

        self.assertFalse(View.objects.filter(pk=view_pk).exists())
        # The pre-existing prefix must survive the revert untouched.
        self.assertTrue(Prefix.objects.filter(pk=prefix_pk).exists())

    # ── ZoneTemplate m2m relations ───────────────────────────────────────────

    def test_zone_template_m2m_merge_and_revert(self):
        """``ZoneTemplate.nameservers`` and ``.record_templates`` round-trip."""
        branch = provision_branch("Zone template", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            nameserver = NameServer.objects.create(name="ns1.example.com")
            record_template = RecordTemplate.objects.create(
                name="A record template",
                record_name="www",
                type=RecordTypeChoices.A,
                value="10.0.0.1",
            )
            zone_template = ZoneTemplate.objects.create(name="Standard")
            zone_template.nameservers.add(nameserver)
            zone_template.record_templates.add(record_template)

        zt_pk = zone_template.pk
        self.assertFalse(ZoneTemplate.objects.filter(pk=zt_pk).exists())

        self._merge(branch)

        zt_main = ZoneTemplate.objects.get(pk=zt_pk)
        self.assertEqual(
            list(zt_main.nameservers.values_list("name", flat=True)),
            ["ns1.example.com"],
        )
        self.assertEqual(
            list(zt_main.record_templates.values_list("name", flat=True)),
            ["A record template"],
        )

        self._revert(branch)

        self.assertFalse(ZoneTemplate.objects.filter(pk=zt_pk).exists())

    # ── DNSSECPolicy.key_templates m2m (carries its own m2m_changed signal) ──

    def test_dnssec_policy_key_templates_m2m_merge_and_revert(self):
        branch = provision_branch("DNSSEC policy", self.MERGE_STRATEGY, self.user)

        with activate_branch(branch), event_tracking(self.request):
            key_template = DNSSECKeyTemplate.objects.create(
                name="KSK",
                type=DNSSECKeyTemplateTypeChoices.TYPE_KSK,
                algorithm=DNSSECKeyTemplateAlgorithmChoices.RSASHA256,
                lifetime=86400,
            )
            policy = DNSSECPolicy.objects.create(name="Default")
            policy.key_templates.add(key_template)

        policy_pk = policy.pk
        self.assertFalse(DNSSECPolicy.objects.filter(pk=policy_pk).exists())

        self._merge(branch)

        policy_main = DNSSECPolicy.objects.get(pk=policy_pk)
        self.assertEqual(
            list(policy_main.key_templates.values_list("name", flat=True)),
            ["KSK"],
        )

        self._revert(branch)

        self.assertFalse(DNSSECPolicy.objects.filter(pk=policy_pk).exists())


# ── Concrete strategy subclasses ─────────────────────────────────────────────


@unittest.skipUnless(HAS_BRANCHING, "netbox-branching is not installed")
class IterativeBranchingTestCase(BaseBranchingTests, TestBase):
    MERGE_STRATEGY = BranchMergeStrategyChoices.ITERATIVE if HAS_BRANCHING else None


@unittest.skipUnless(HAS_BRANCHING, "netbox-branching is not installed")
class SquashBranchingTestCase(BaseBranchingTests, TestBase):
    MERGE_STRATEGY = BranchMergeStrategyChoices.SQUASH if HAS_BRANCHING else None


# ── Sync (main → branch) ─────────────────────────────────────────────────────


@unittest.skipUnless(HAS_BRANCHING, "netbox-branching is not installed")
class BranchSyncTestCase(BranchingTestBase, TestBase):
    """Changes made in main after provisioning become visible after ``sync()``."""

    def test_main_changes_synced_to_branch(self):
        branch = provision_branch(
            "Sync", BranchMergeStrategyChoices.ITERATIVE, self.user
        )

        # Create a nameserver in main *after* the branch was provisioned. It
        # must be created inside event_tracking so an ObjectChange is recorded
        # for sync() to replay into the branch.
        with event_tracking(make_request(self.user)):
            nameserver = NameServer.objects.create(name="ns-late.example.com")
        ns_pk = nameserver.pk

        # Not yet visible inside the branch.
        with activate_branch(branch):
            self.assertFalse(NameServer.objects.filter(pk=ns_pk).exists())

        branch.sync(user=self.user, commit=True)

        with activate_branch(branch):
            self.assertTrue(NameServer.objects.filter(pk=ns_pk).exists())
