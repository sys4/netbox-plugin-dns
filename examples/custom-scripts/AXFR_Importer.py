#!/usr/bin/env python3

# +
# AXFR importer script for NetBox DNS
#
# CAUTION: This is *not* production quality code. It does not contain proper
# error handling and is only very superficially tested. Using it in production
# will likely lead to data loss or corruption and will almost certainly not
# fulfill any practical purpose.
#
# This is example code for importing a zone into NetBox DNS using an AXFR
# from an authoritatve name server.
# -

from dns import rdataclass, rdatatype, tsig, tsigkeyring
from dns.query import xfr
from dns.zone import from_xfr

from extras.scripts import BooleanVar, ChoiceVar, ObjectVar, Script, StringVar
from netbox_dns.models import NameServer, Record, View, Zone

name = "AXFR Zone Importer"


class AXFRImporter(Script):
    class Meta:
        name = "AXFR Zone Importer"
        description = "This custom script can be used to import a zone directly from a name server"
        commit_default = True

    view = ObjectVar(
        model=View,
        default=View.get_default_view().pk,
        label="Destination view",
    )
    zone = StringVar(
        min_length=1,
        max_length=255,
        required=True,
        label="Source zone name",
    )
    nameserver = StringVar(
        min_length=1,
        max_length=255,
        required=True,
        label="Source name server IP address",
    )
    tsig_key_name = StringVar(
        required=False,
        label="TSIG key name",
    )
    tsig_key = StringVar(
        required=False,
        label="TSIG key",
    )
    tsig_key_algorithm = ChoiceVar(
        choices=(
            (tsig.HMAC_MD5, "HMAC_MD5"),
            (tsig.HMAC_SHA1, "HMAC_SHA1"),
            (tsig.HMAC_SHA224, "HMAC_SHA224"),
            (tsig.HMAC_SHA256, "HMAC_SHA256"),
            (tsig.HMAC_SHA256_128, "HMAC_SHA256_128"),
            (tsig.HMAC_SHA384, "HMAC_SHA384"),
            (tsig.HMAC_SHA384_192, "HMAC_SHA384_192"),
            (tsig.HMAC_SHA512, "HMAC_SHA512"),
            (tsig.HMAC_SHA512_256, "HMAC_SHA512_256"),
        ),
        default=(tsig.HMAC_SHA256, "HMAC_SHA256"),
        label="TSIG key algorithm",
    )
    relativize_names = BooleanVar(
        description="Use relative names in the import",
        label="Relativize Names",
        default=True,
    )
    disable_ptr = BooleanVar(
        description="Disable automatic creation of PTR records",
        label="Disable PTR",
        default=True,
    )

    def _create_nameserver(self, name, zone=None):
        if zone is not None:
            origin = zone.origin

            self.log_debug(f"Derelativizing nameserver name {name} to {origin}")
            name = name.derelativize(origin=origin).to_text().rstrip(".")

        self.log_debug(f"Checking for name server {name}")
        nameserver = NameServer.objects.filter(name=name).first()
        self.log_debug(nameserver)
        if not nameserver:
            nameserver = NameServer.objects.create(name=name)

        return nameserver

    def run(self, data, commit):
        view = data.get("view")
        zone_name = data.get("zone")

        if Zone.objects.filter(view=view, name=zone_name).exists():
            self.log_failure(
                f"Zone {zone_name} already exists in view {view.name}, cannot import again"
            )
            return

        tsig_key_name = data.get("tsig_key_name")
        tsig_key = data.get("tsig_key")

        if tsig_key_name and not tsig_key:
            self.log_failure(
                "If a TSIG Key Name is specified, a TSIG Key must be specified as well"
            )
            return

        keyring = tsigkeyring.from_text(
            {
                tsig_key_name: tsig_key,
            }
        )

        nameserver = data.get("nameserver")
        relativize = data.get("relativize_names")
        disable_ptr = data.get("disable_ptr")

        tsig_params = {}
        if tsig_key_name:
            tsig_params["keyring"] = keyring
            tsig_params["keyname"] = tsig_key_name
            tsig_params["keyalgorithm"] = data.get("tsig_key_algorithm")

        self.log_info(f"Importing zone {zone_name} from name server {nameserver}")

        try:
            axfr_zone = from_xfr(
                xfr=xfr(
                    nameserver,
                    zone_name,
                    relativize=relativize,
                    **tsig_params,
                ),
                relativize=relativize,
            )
        except Exception:
            self.log_failure("Zone transfer failed")
            return

        origin = axfr_zone.origin
        soa = axfr_zone.get_soa()

        soa_mname = self._create_nameserver(name=soa.mname, zone=axfr_zone)

        self.log_info(f"Creating zone {zone_name}")
        zone = Zone.objects.create(
            name=zone_name,
            view=view,
            soa_mname=soa_mname,
            soa_rname=soa.rname.derelativize(origin),
            soa_refresh=soa.refresh,
            soa_retry=soa.retry,
            soa_expire=soa.expire,
            soa_minimum=soa.minimum,
            soa_serial=soa.serial,
            soa_serial_auto=False,
        )

        for name, node in axfr_zone.nodes.items():
            name = name.relativize(origin)
            for rdataset in node.rdatasets:
                if rdataset.rdclass != rdataclass.IN:
                    continue

                if rdataset.rdtype in (
                    rdatatype.SOA,
                    rdatatype.RRSIG,
                    rdatatype.NSEC3,
                    rdatatype.NSEC3PARAM,
                    rdatatype.CDS,
                    65534,
                ):
                    continue

                if rdataset.rdtype in (
                    rdatatype.A,
                    rdatatype.AAAA,
                ):
                    record_disable_ptr = disable_ptr
                else:
                    record_disable_ptr = False

                rdtype = rdatatype.to_text(rdataset.rdtype)
                ttl = rdataset.ttl if rdataset.ttl != zone.default_ttl else None

                for item in rdataset:
                    if rdataset.rdtype == rdatatype.NS:
                        zone.nameservers.add(
                            self._create_nameserver(
                                name=item.target.derelativize(origin), zone=axfr_zone
                            )
                        )
                        continue

                    value = item.to_text()

                    self.log_debug(
                        f"Creating {name} record: TTL={ttl} RDType={rdtype} RData={value}"
                    )
                    Record.objects.create(
                        name=name,
                        zone=zone,
                        type=rdtype,
                        ttl=ttl,
                        value=value,
                        disable_ptr=record_disable_ptr,
                    )
