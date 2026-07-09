from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from netbox.context import current_request
from netbox_dns.branching import dns_branch_replay_active
from netbox_dns.models import DNSSECKeyTemplate, DNSSECPolicy
from netbox_dns.validators import validate_key_template_assignment
from utilities.exceptions import AbortRequest


@receiver(m2m_changed, sender=DNSSECPolicy.key_templates.through)
def dnssec_policy_key_templates_changed(action, instance, pk_set, **kwargs):
    if dns_branch_replay_active():
        # The assignment was already validated when it was made in the branch;
        # don't re-validate while replaying a merge/sync/revert.
        return

    request = current_request.get()

    key_templates = instance.key_templates.all()
    match action:
        case "pre_remove":
            key_templates = key_templates.exclude(pk__in=pk_set)
        case "pre_add":
            key_templates |= DNSSECKeyTemplate.objects.filter(pk__in=pk_set)
        case _:
            return

    try:
        validate_key_template_assignment(key_templates)
    except ValidationError as exc:
        if request is not None:
            raise AbortRequest(exc)

        raise exc
