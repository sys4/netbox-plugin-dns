import re
import textwrap

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from dns import name as dns_name
from dns import rdata
from dns.exception import SyntaxError

from netbox.plugins.utils import get_plugin_config
from netbox_dns.choices import RecordClassChoices, RecordTypeChoices
from netbox_dns.validators import (
    validate_domain_name,
    validate_fqdn,
    validate_generic_name,
)

MAX_TXT_LENGTH = 255

__all__ = ("validate_record_value",)


def validate_record_value(record):
    def _validate_idn(name):
        try:
            name.to_unicode()
        except dns_name.IDNAException as exc:
            raise ValidationError(
                _("{name} is not a valid IDN: {error}.").format(
                    name=name.to_text(), error=exc
                )
            )

    def _split_text_value(value):
        # +
        # Text values longer than 255 characters need to be broken up for TXT and
        # SPF records.
        # First, in case they had been split into separate strings, reassemble the
        # original (long) value, then split it into chunks of a maximum length of
        # 255 (preferably at word boundaries), and then build a sequence of partial
        # strings enclosed in double quotes and separated by space.
        #
        # See https://datatracker.ietf.org/doc/html/rfc4408#section-3.1.3 for details.
        # -
        raw_value = "".join(re.findall(r'"([^"]+)"', value))
        if not raw_value:
            raw_value = value

        return " ".join(
            f'"{part}"'
            for part in textwrap.wrap(raw_value, MAX_TXT_LENGTH, drop_whitespace=False)
        )

    if record.type in (RecordTypeChoices.CUSTOM_TYPES):
        return

    if record.type in (RecordTypeChoices.TXT, RecordTypeChoices.SPF):
        if not (record.value.isascii() and record.value.isprintable()):
            raise ValidationError(
                _(
                    "Record value {value} for a type {type} record is not a printable ASCII string."
                ).format(value=record.value, type=record.type)
            )

        if len(record.value) <= MAX_TXT_LENGTH:
            return

        try:
            unquoted_value = record.value.lstrip('"').rstrip('"')
            rr = rdata.from_text(
                RecordClassChoices.IN, record.type, f'"{unquoted_value}"'
            )
        except SyntaxError as exc:
            if str(exc) == "string too long":
                record.value = _split_text_value(record.value)

    try:
        rr = rdata.from_text(RecordClassChoices.IN, record.type, record.value)
    except SyntaxError as exc:
        raise ValidationError(
            _(
                "Record value {value} is not a valid value for a {type} record: {error}."
            ).format(value=record.value, type=record.type, error=exc)
        )

    if record.type not in (RecordTypeChoices.TXT, RecordTypeChoices.SPF):
        record.value = rr.to_text()

    skip_name_validation = record.type in get_plugin_config(
        "netbox_dns", "tolerate_non_rfc1035_types", default=[]
    )

    match record.type:
        case RecordTypeChoices.CNAME:
            _validate_idn(rr.target)
            if not skip_name_validation:
                validate_domain_name(
                    rr.target.to_text(),
                    always_tolerant=True,
                    allow_empty_label=True,
                )

        case (
            RecordTypeChoices.NS
            | RecordTypeChoices.HTTPS
            | RecordTypeChoices.SRV
            | RecordTypeChoices.SVCB
        ):
            _validate_idn(rr.target)
            if not skip_name_validation:
                validate_domain_name(rr.target.to_text(), always_tolerant=True)

        case RecordTypeChoices.DNAME:
            _validate_idn(rr.target)
            if not skip_name_validation:
                validate_domain_name(
                    rr.target.to_text(), always_tolerant=True, zone_name=True
                )

        case RecordTypeChoices.PTR | RecordTypeChoices.NSAP_PTR:
            _validate_idn(rr.target)
            if not skip_name_validation:
                validate_fqdn(rr.target.to_text(), always_tolerant=True)

        case RecordTypeChoices.MX | RecordTypeChoices.RT | RecordTypeChoices.KX:
            _validate_idn(rr.exchange)
            if not skip_name_validation:
                validate_domain_name(rr.exchange.to_text(), always_tolerant=True)

        case RecordTypeChoices.NSEC:
            _validate_idn(rr.next)
            if not skip_name_validation:
                validate_domain_name(rr.next.to_text(), always_tolerant=True)

        case RecordTypeChoices.RP:
            _validate_idn(rr.mbox)
            _validate_idn(rr.txt)
            if not skip_name_validation:
                validate_domain_name(rr.mbox.to_text(), always_tolerant=True)
                validate_domain_name(rr.txt.to_text(), always_tolerant=True)

        case RecordTypeChoices.NAPTR:
            _validate_idn(rr.replacement)
            if not skip_name_validation:
                validate_generic_name(rr.replacement.to_text(), always_tolerant=True)

        case RecordTypeChoices.PX:
            _validate_idn(rr.map822)
            _validate_idn(rr.mapx400)
            if not skip_name_validation:
                validate_domain_name(rr.map822.to_text(), always_tolerant=True)
                validate_domain_name(rr.mapx400.to_text(), always_tolerant=True)
