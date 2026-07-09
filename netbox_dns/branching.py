"""
Integration hooks for the `NetBox Branching`_ plugin.

NetBox Branching decides whether a model's rows live in a branch's schema by
checking whether the model uses NetBox's change-logging mixin
(``ChangeLoggingMixin``).  That heuristic misses the auto-generated
many-to-many *through* models behind fields such as ``Zone.nameservers`` and
``View.prefixes``: those are plain ``django.db.models.Model`` subclasses, so
without help Branching routes their queries to the *main* schema even while a
branch is active.

The consequences are exactly the merge failures reported against the plugin:
the m2m rows written inside a branch (e.g. the nameservers assigned to a zone)
land in main rather than the branch, and the reconciliation logic in
``Zone.update_ns_records()`` / ``NameServer.save()`` -- which reads a zone's own
nameservers and NS records back out through those relations -- sees the wrong
schema.  When the branch is later merged the change set doesn't apply cleanly.

The resolver below marks every NetBox DNS model -- both the change-logged
primary models and their m2m through models -- as branchable, so all of their
queries are routed to the active branch's schema and the branch merges cleanly.

Everything here is a no-op unless netbox-branching is installed; the caller in
``DNSConfig.ready()`` guards registration with ``try/except ImportError``.

.. _NetBox Branching: https://github.com/netboxlabs/netbox-branching
"""

import threading
from functools import cache

__all__ = (
    "dns_branch_replay_active",
    "supports_branching_resolver",
)

APP_LABEL = "netbox_dns"


# ── Replay guard ─────────────────────────────────────────────────────────────
#
# NetBox DNS keeps derived data -- the managed SOA and NS records, PTR records,
# and auto-incrementing SOA serials -- in sync through side effects in the
# ``save()`` / ``delete()`` methods and ``m2m_changed`` receivers of its models.
#
# When NetBox Branching merges (or syncs, or reverts) a branch it *replays* the
# branch's recorded changes onto the target schema.  Those recorded changes
# already include every derived record the side effects produced inside the
# branch.  If the side effects run again during replay they recreate that
# derived data a second time, colliding with the replayed copy -- e.g. "there
# is already an active SOA record for name @".  This is the root cause of the
# reported merge failures.
#
# The flag below is raised for the duration of a merge / sync / revert (via the
# Branching pre-/post- signals wired up in ``_register_branching_hooks``).
# While it is set, the DNS models persist rows but skip their reconciliation
# side effects, letting the replayed changelog reproduce the branch state
# exactly.  It is a thread-local boolean so it never bleeds across the
# concurrent requests/workers that might be running outside the merge.

_replay_state = threading.local()


def dns_branch_replay_active():
    """
    Return ``True`` while a NetBox Branching merge / sync / revert is replaying
    changes in the current thread.  DNS model side effects check this to avoid
    regenerating derived records that the replay already carries.

    Always ``False`` when netbox-branching isn't installed (nothing ever sets
    the flag), so this is a cheap no-op in non-branching deployments.
    """
    return getattr(_replay_state, "active", False)


def _enter_replay(**kwargs):
    _replay_state.active = True


def _exit_replay(**kwargs):
    _replay_state.active = False


@cache
def _m2m_through_models():
    """
    Return the set of auto-generated m2m *through* model classes owned by the
    NetBox DNS app (e.g. the through model behind ``Zone.nameservers``).

    Only through models that live in the ``netbox_dns`` app are returned.
    Shared NetBox through models reachable from the DNS models -- notably
    ``extras.TaggedItem`` behind the ``tags`` field -- are excluded: those are
    branch-aware in their own right (Branching lists ``extras.taggeditem`` in
    its ``INCLUDE_MODELS``), so they must not be claimed here.

    Computed once and cached; the app registry is fully populated by the time a
    resolver is first invoked, so iterating it here is safe.
    """
    from django.apps import apps

    through_models = set()
    for model in apps.get_app_config(APP_LABEL).get_models():
        for field in model._meta.local_many_to_many:
            through = getattr(field.remote_field, "through", None)
            if through is not None and through._meta.app_label == APP_LABEL:
                through_models.add(through)

    return through_models


def supports_branching_resolver(model):
    """
    Branching resolver registered via
    ``netbox_branching.utilities.register_branching_resolver``.

    Signature: ``resolver(model) -> bool | None``

    * ``True``  -- model is branchable, route its queries to the active branch
    * ``None``  -- defer to the next resolver / Branching's default heuristic

    A NetBox DNS model is branchable when it either

    * inherits NetBox's ``ChangeLoggingMixin`` (all of the plugin's primary
      models do, via ``PrimaryModel``), or
    * is one of the auto-generated m2m through models (plain ``models.Model``
      subclasses that Branching's default heuristic would otherwise route to
      the main schema, breaking merges).

    Models from other apps -- including the m2m *targets* that live outside
    ``netbox_dns`` such as ``ipam.Prefix`` -- return ``None`` so their own
    change-logging status (and any other plugin's resolver) decides.
    """
    from netbox.models.features import ChangeLoggingMixin

    meta = getattr(model, "_meta", None)
    if meta is None or meta.app_label != APP_LABEL:
        return None

    if issubclass(model, ChangeLoggingMixin):
        return True

    if model in _m2m_through_models():
        return True

    return None
