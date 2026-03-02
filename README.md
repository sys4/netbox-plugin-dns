# NetBox DNS

The NetBox DNS plugin enables NetBox to manage operational DNS data such as name servers, zones, records and views, as well as registration data for domains. It can automate tasks like creating PTR records, generating zone serial numbers, NS and SOA records, as well as validate names and values values for resource records to ensure zone data is consistent, up-to-date and compliant with to the relevant RFCs.

<div align="center">
<a href="https://pypi.org/project/netbox-plugin-dns/"><img src="https://img.shields.io/pypi/v/netbox-plugin-dns" alt="PyPi"/></a>
<a href="https://github.com/sys4/netbox-plugin-dns/stargazers"><img src="https://img.shields.io/github/stars/sys4/netbox-plugin-dns?style=flat" alt="Stars Badge"/></a>
<a href="https://github.com/sys4/netbox-plugin-dns/network/members"><img src="https://img.shields.io/github/forks/sys4/netbox-plugin-dns?style=flat" alt="Forks Badge"/></a>
<a href="https://github.com/sys4/netbox-plugin-dns/issues"><img src="https://img.shields.io/github/issues/sys4/netbox-plugin-dns" alt="Issues Badge"/></a>
<a href="https://github.com/sys4/netbox-plugin-dns/pulls"><img src="https://img.shields.io/github/issues-pr/sys4/netbox-plugin-dns" alt="Pull Requests Badge"/></a>
<a href="https://github.com/sys4/netbox-plugin-dns/graphs/contributors"><img alt="GitHub contributors" src="https://img.shields.io/github/contributors/sys4/netbox-plugin-dns?color=2b9348"></a>
<a href="https://github.com/sys4/netbox-plugin-dns/blob/master/LICENSE"><img src="https://img.shields.io/github/license/sys4/netbox-plugin-dns?color=2b9348" alt="License Badge"/></a>
<a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style Black"/></a>
<a href="https://pepy.tech/project/netbox-plugin-dns"><img alt="Downloads" src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns?period=total&left_color=BLACK&right_color=BLUE&left_text=Downloads"></a>
<a href="https://pepy.tech/project/netbox-plugin-dns"><img alt="Downloads/Week" src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns?period=monthly&left_color=BLACK&right_color=BLUE&left_text=Downloads%2fMonth"></a>
<a href="https://pepy.tech/project/netbox-plugin-dns"><img alt="Downloads/Month" src="https://static.pepy.tech/personalized-badge/netbox-plugin-dns?period=weekly&left_color=BLACK&right_color=BLUE&left_text=Downloads%2fWeek"></a>
</div>

> [!WARNING]
> **As a result of some issues with NetBox Branching still under investigation, NetBox DNS is currently not compatible with the new NetBox Branching plugin.**
> This affects multiple aspects of the branching functionality, and currently there is no workaround. Do not try to use NetBox Branching together with NetBox DNS until these issues are resolved.
> This warning will be updated as soon as the situation is resolved.

## Objectives
NetBox DNS is designed to be the 'DNS Source of Truth' analogous to NetBox being the 'Network Source of Truth'.

The plugin stores information about DNS name servers, DNS views and zones, and DNS records, making it a data source for automatic provisioning of DNS instances. Registration information about DNS registrars and contacts for DNS domains can also be stored and associated with zones.

The main focus of the plugin is to ensure the quality of the data stored in it. To achieve this, there are many validation and automation mechanisms in place:

* Validation of record names and values
* Automatic maintenance of PTR records for IPv6 and IPv4 address records
* Automatic generation of SOA records, optionally including the serial number of the zone data
* Validation of changes to the SOA SERIAL number, whether they are done automatically or manually
* Validation of record types such as CNAME and singletons, to ensure DNS zone validity
* Support for [RFC 2317](https://datatracker.ietf.org/doc/html/rfc2317) delegation of PTR zones for IPv4 subnets longer than 24 bits
* Templating for zones and records enables faster creations of zones with given boilerplate object relations, such as name servers, tags, tenants or registration information, or records like standard SPF or MX records that are the same for a subset of zones
* IPAM DNSsync can be used to automatically create address and pointer records for IP addresses by assigning prefixes to DNS views. When an IP address has a DNS name assigned and there are zones with matching names in the DNS views linked to the IP address' prefix, a matching DNS record will be created in these zones
* DNSSEC support for storing configuration data relevant to DNSSEC operation in NetBox DNS

Other main features include:

* Support for BIND views, providing lightweight namespaces for zones
* Support for IDN, including the validation of punycode names
* Full support for the NetBox REST and GraphQL APIs
* Support for all major NetBox features such as global search, tenancy, change logs, tagging, journaling etc.

## Non-objectives
In the same way as NetBox is not a network management application, NetBox DNS does not provide any functionality to manage specific name servers or DNS service providers or to generate input such as configuration and zone files for them. The focus is on the completeness and integrity of the data needed to run DNS zones, not on the peculiarities of a plethora of servers and services that actually use the data. This functionality is left to specialized integration tools, or in many cases it can be easily implemented using Ansible or similar tools based on NetBox DNS data. Example code for some simple use cases is provided.

For integration with a large number of DNS server implementations integration tools like [octodns-netbox-dns](https://pypi.org/project/octodns-netbox-dns/) are available.

For RFC9432 compatible DNS Servers like BIND, a related plugin [netbox-plugin-bind-provisioner](https://github.com/Suraxius/netbox-plugin-bind-provisioner) provides direct integration using DNS native zone distribution.

## Requirements

* NetBox 4.5.0 or higher
* Python 3.12 or higher

## Compatibility with NetBox Versions

NetBox Version | NetBox DNS Version | Comment
-------------- | ------------------ | -------
3.5            | 0.22               |
3.6            | 0.22               |
3.7            | 0.22               |
4.0 - 4.1      | 1.0                | Supports legacy IPAM Coupling
4.0 - 4.1      | 1.1                | Supports IPAM DNSsync
4.2            | 1.2                |
4.3            | 1.3 - 1.4          |
4.4            | 1.4                |
4.5            | 1.5                |

## Installation & Configuration

### Installation

```
$ source /opt/netbox/venv/bin/activate
(venv) $ pip install netbox-plugin-dns
```

### NetBox Configuration

Add the plugin to the NetBox config. `~/netbox/configuration.py`

```python
PLUGINS = [
    "netbox_dns",
]
```

To permanently keep the plugin installed when updating NetBox via `upgrade.sh`:

```
echo netbox-plugin-dns >> ~/netbox/local_requirements.txt
```

To add the required netbox_dns tables to your database run the following command from your NetBox directory:

```
./manage.py migrate
```

Full documentation on using plugins with NetBox: [Using Plugins - NetBox Documentation](https://netbox.readthedocs.io/en/stable/plugins/)

## Contribute

Contributions are always welcome! Please see the [Contribution Guidelines](CONTRIBUTING.md)

## Documentation

For further information, please refer to the full documentation: [Using NetBox DNS](docs/using_netbox_dns.md)

## License

MIT
