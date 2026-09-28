from django.utils.translation import gettext as _
from rest_framework.routers import APIRootView

from ipam.filtersets import PrefixFilterSet
from ipam.models import Prefix
from netbox.api.viewsets import NetBoxModelViewSet
from netbox_dns.api.serializers import (
    DNSSECKeyTemplateSerializer,
    DNSSECPolicySerializer,
    NameServerSerializer,
    PrefixSerializer,
    RecordSerializer,
    RecordTemplateSerializer,
    RegistrarSerializer,
    RegistrationContactSerializer,
    ViewSerializer,
    ZoneSerializer,
    ZoneTemplateSerializer,
)
from netbox_dns.filtersets import (
    DNSSECKeyTemplateFilterSet,
    DNSSECPolicyFilterSet,
    NameServerFilterSet,
    RecordFilterSet,
    RecordTemplateFilterSet,
    RegistrarFilterSet,
    RegistrationContactFilterSet,
    ViewFilterSet,
    ZoneFilterSet,
    ZoneTemplateFilterSet,
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
from utilities.exceptions import AbortRequest


class NetBoxDNSRootView(APIRootView):
    def get_view_name(self):
        return "NetBoxDNS"


class ViewViewSet(NetBoxModelViewSet):
    queryset = View.objects.all()
    serializer_class = ViewSerializer
    filterset_class = ViewFilterSet


class ZoneViewSet(NetBoxModelViewSet):
    queryset = Zone.objects.prefetch_related("view", "nameservers", "soa_mname")
    serializer_class = ZoneSerializer
    filterset_class = ZoneFilterSet


class NameServerViewSet(NetBoxModelViewSet):
    queryset = NameServer.objects.prefetch_related("zones")
    serializer_class = NameServerSerializer
    filterset_class = NameServerFilterSet


class RecordViewSet(NetBoxModelViewSet):
    queryset = Record.objects.prefetch_related("zone", "zone__view")
    serializer_class = RecordSerializer
    filterset_class = RecordFilterSet

    def perform_destroy(self, instance):
        if instance.managed:
            raise AbortRequest(
                _("{object} is managed, refusing deletion").format(object=instance)
            )

        super().perform_destroy(instance)


class RegistrarViewSet(NetBoxModelViewSet):
    queryset = Registrar.objects.all()
    serializer_class = RegistrarSerializer
    filterset_class = RegistrarFilterSet


class RegistrationContactViewSet(NetBoxModelViewSet):
    queryset = RegistrationContact.objects.all()
    serializer_class = RegistrationContactSerializer
    filterset_class = RegistrationContactFilterSet


class ZoneTemplateViewSet(NetBoxModelViewSet):
    queryset = ZoneTemplate.objects.all()
    serializer_class = ZoneTemplateSerializer
    filterset_class = ZoneTemplateFilterSet


class RecordTemplateViewSet(NetBoxModelViewSet):
    queryset = RecordTemplate.objects.all()
    serializer_class = RecordTemplateSerializer
    filterset_class = RecordTemplateFilterSet


class DNSSECKeyTemplateViewSet(NetBoxModelViewSet):
    queryset = DNSSECKeyTemplate.objects.all()
    serializer_class = DNSSECKeyTemplateSerializer
    filterset_class = DNSSECKeyTemplateFilterSet


class DNSSECPolicyViewSet(NetBoxModelViewSet):
    queryset = DNSSECPolicy.objects.all()
    serializer_class = DNSSECPolicySerializer
    filterset_class = DNSSECPolicyFilterSet


class PrefixViewSet(NetBoxModelViewSet):
    queryset = Prefix.objects.all()
    serializer_class = PrefixSerializer
    filterset_class = PrefixFilterSet
