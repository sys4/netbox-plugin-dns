"""
Shared infrastructure for the NetBox DNS branching integration tests.

These tests exercise the branching resolver registered by
``netbox_dns.branching`` end-to-end: they provision a real NetBox Branching
branch (a separate PostgreSQL schema), make DNS changes inside it, and merge /
revert the branch back to main.

They are skipped automatically when netbox-branching is not installed, so the
plugin's regular test suite stays clean in environments that don't use it.

``TransactionTestCase`` (not ``TestCase``) is required: branch schemas live in
separate PostgreSQL schemas backed by distinct database connections that cannot
be rolled back inside a single SAVEPOINT-based transaction.
"""

import logging
import os
import time
import uuid

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.management import create_contenttypes
from django.db import connection, connections
from django.test import RequestFactory, TransactionTestCase
from django.urls import reverse

try:
    from netbox_branching.choices import BranchStatusChoices
    from netbox_branching.models import Branch

    HAS_BRANCHING = True
except ImportError:
    HAS_BRANCHING = False

logger = logging.getLogger(__name__)
User = get_user_model()

# When netbox-branching is not installed, use ``object`` as the concrete base so
# Django's test runner doesn't try to run the (skipped) TransactionTestCase
# machinery — keeping it fully isolated from the plugin's other test modules.
TestBase = TransactionTestCase if HAS_BRANCHING else object

# Provisioning timeout for branch tests. Override via the
# ``NETBOX_DNS_BRANCH_PROVISION_TIMEOUT`` env var (seconds) when CI is slow.
BRANCH_PROVISION_TIMEOUT = float(
    os.environ.get("NETBOX_DNS_BRANCH_PROVISION_TIMEOUT", "30")
)


def make_request(user):
    """Return a fresh request object suitable for ``event_tracking``."""
    request = RequestFactory().get(reverse("home"))
    request.id = uuid.uuid4()
    request.user = user
    return request


def provision_branch(name, merge_strategy=None, user=None, timeout=None):
    """
    Create a branch and wait for it to reach ``READY`` status.

    ``merge_strategy`` is optional (the ``Branch`` field is nullable); only
    tests that actually merge or revert need to pass one.
    """
    if timeout is None:
        timeout = BRANCH_PROVISION_TIMEOUT

    branch = Branch(name=name, merge_strategy=merge_strategy)
    branch.save(provision=False)
    branch.provision(user=user)

    deadline = time.time() + timeout
    while time.time() < deadline:
        branch.refresh_from_db()
        if branch.status == BranchStatusChoices.READY:
            return branch
        time.sleep(0.1)

    raise TimeoutError(
        f"Branch {name!r} did not reach READY within {timeout:.0f}s "
        f"(status={branch.status!r})"
    )


def _recreate_contenttypes():
    """
    Recreate ContentType rows for all installed apps.

    ``TransactionTestCase`` flushes every table between tests; recreating the
    ContentTypes (idempotently, via ``get_or_create``) lets subsequent test
    classes look up ObjectType rows again without the duplicate-key violations
    that ``serialized_rollback`` can cause under the parallel runner.
    """
    for app_config in django_apps.get_app_configs():
        create_contenttypes(app_config, verbosity=0)


def _close_branch_connections():
    """Best-effort close of any open branch database connections."""
    from django.db.utils import DatabaseError

    for branch in Branch.objects.all():
        try:
            connections[branch.connection_name].close()
        except DatabaseError:
            logger.debug(
                "failed to close branch connection %r",
                branch.connection_name,
                exc_info=True,
            )


def _drop_branch_schemas():
    """
    Drop leftover NetBox Branching branch schemas before the database flush.

    Each provisioned branch gets its own PostgreSQL schema holding copies of
    branch-aware tables that carry FK references into the main schema.  If a
    test errors before deleting its branch, ``TransactionTestCase``'s TRUNCATE
    fails with "cannot truncate a table referenced in a foreign key
    constraint".  In the test database the only non-system schemas are branch
    schemas, so dropping all of them is safe.
    """
    # Close all non-default connections; branch connections may still be open.
    for alias in list(connections):
        if alias != "default":
            try:
                connections[alias].close()
            except Exception:
                pass

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name NOT IN (
                    'public', 'pg_catalog', 'information_schema', 'pg_toast'
                )
                AND schema_name NOT LIKE 'pg_%%'
                """
            )
            schemas = [row[0] for row in cursor.fetchall()]

        if not schemas:
            return

        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '10s'")
            for schema in schemas:
                try:
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                except Exception:
                    logger.warning(
                        "could not drop branch schema %r", schema, exc_info=True
                    )
    except Exception:
        logger.warning("_drop_branch_schemas failed", exc_info=True)


def _reset_netbox_request_context():
    """
    Clear NetBox's request-scoped ContextVars.

    ``netbox.context_managers.event_tracking()`` sets ``current_request`` on
    entry but only clears it after ``yield`` — so an exception inside the
    ``with`` block leaves it pointing at a request whose user row is truncated
    by the following flush, which would make the next test's ObjectChange
    creation fail an FK check on ``user_id``.
    """
    try:
        from netbox.context import current_request, events_queue, query_cache
    except ImportError:
        return

    current_request.set(None)
    events_queue.set({})
    try:
        query_cache.set(None)
    except AttributeError:
        logger.debug("netbox.context.query_cache has no .set(); skipping reset")


class BranchingTestBase:
    """
    Common per-test lifecycle for the branching-aware DNS test classes.

    Concrete test classes must also inherit from ``TransactionTestCase`` (via
    ``TestBase``) — branch schemas can't be rolled back inside a SAVEPOINT.
    """

    def setUp(self):
        super().setUp()
        _reset_netbox_request_context()
        _recreate_contenttypes()
        self.user = User.objects.create_user(username="dns-branching-testuser")
        self.request = make_request(self.user)

        # NetBox DNS ships a default View (created by a data migration) that
        # ``Zone.clean_fields()`` auto-assigns when a zone is saved without an
        # explicit view.  TransactionTestCase flushes that migration data
        # between tests, so recreate it here — before any branch is
        # provisioned, so it's replicated into the branch schema too.
        from netbox_dns.models import View

        View.objects.get_or_create(
            default_view=True,
            defaults={"name": "_default_", "description": "Default View"},
        )

    def tearDown(self):
        _reset_netbox_request_context()
        # Defensively clear the branching replay guard so a test whose merge or
        # revert raised (leaving post_merge/post_revert unfired) can't leak an
        # active-replay flag into the next test.
        from netbox_dns.branching import _exit_replay

        _exit_replay()
        _close_branch_connections()
        # Remove ObjectChange rows created during the test (merge/revert writes
        # them into main referencing the test user); leaving them behind makes
        # the serialized_rollback snapshot fail an FK check after the flush.
        from core.models import ObjectChange

        ObjectChange.objects.all().delete()
        super().tearDown()

    def _fixture_teardown(self):
        # Drop lingering branch schemas before Django's flush TRUNCATEs the
        # main-schema tables they reference, then restore ContentTypes for any
        # test class that follows on the same worker.
        _drop_branch_schemas()
        super()._fixture_teardown()
        _recreate_contenttypes()
