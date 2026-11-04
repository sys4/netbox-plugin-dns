#!/usr/bin/env python3

# +
# Zone file importer script for NetBox DNS
#
# CAUTION: This is *not* production quality code. It does not contain proper
# error handling and is only very superficially tested. Using it in production
# will likely lead to data loss or corruption and will almost certainly not
# fulfill any practical purpose.
#
# This is example code for importing a zone from a master zone file into
# NetBox DNS.
# -

import io

from django.core.exceptions import ValidationError
from dns import name as dns_name
from dns import rdataclass, rdatatype
from dns.zone import from_file

from extras.scripts import BooleanVar, FileVar, ObjectVar, Script, StringVar
from netbox_dns.models import NameServer, Record, View, Zone

name = "Zone File Importer"


class ZoneFileImporter(Script):
    class Meta:
        name = "Zone File Importer"
        description = (
            "This custom script can be used to import a zone from a master zone file"
        )
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
    zone_file = FileVar(
        description="Zone file to import from",
        required=True,
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
                f"Zone {zone_name} already exists in view {view.name}, cannot import it again"
            )
            return

        zone_file = data.get("zone_file")
        relativize = data.get("relativize_names")
        disable_ptr = data.get("disable_ptr")

        self.log_info(f"Importing zone {zone_name} from file {zone_file}")
        try:
            with io.TextIOWrapper(zone_file, encoding="utf-8") as decoded_zone_file:
                file_zone = from_file(
                    f=decoded_zone_file,
                    origin=dns_name.from_text(zone_name),
                    relativize=relativize,
                )
        except Exception as exc:
            self.log_failure(f"Zone file import failed: {exc}")
            return

        origin = file_zone.origin
        soa = file_zone.get_soa()

        soa_mname = self._create_nameserver(name=soa.mname, zone=file_zone)

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

        for name, node in file_zone.nodes.items():
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
                        try:
                            nameserver_name = item.target.derelativize(origin)
                            zone.nameservers.add(
                                self._create_nameserver(
                                    name=nameserver_name, zone=file_zone
                                )
                            )
                        except ValidationError as exc:
                            self.log_failure(
                                f"Error occurred creating nameserver {nameserver_name}: {exc}"
                            )
                        continue

                    value = item.to_text()

                    self.log_debug(
                        f"Creating {name} record: TTL={ttl} RDType={rdtype} RData={value}"
                    )
                    try:
                        Record.objects.create(
                            name=name,
                            zone=zone,
                            type=rdtype,
                            ttl=ttl,
                            value=value,
                            disable_ptr=record_disable_ptr,
                        )
                    except Exception as exc:
                        self.log_failure(
                            f"Error occurred creating {rdtype} record {name} in zone {zone.name}: {exc}"
                        )

        return
