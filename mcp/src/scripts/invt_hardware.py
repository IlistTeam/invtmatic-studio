# -*- coding: utf-8 -*-
"""Explicit, address-scoped physical PLC discovery. No login or runtime changes."""
import os
import re
import time
import scriptengine as se
from invt_executor import with_executor

OPS = ('plc_gateways', 'plc_find')
try:
    string_types = (basestring,)
    text = unicode
except NameError:
    string_types = (str,)
    text = str


def allowed_address(value):
    if not isinstance(value, string_types) or not re.match(r'^(?:0|[1-9][0-9]{0,2})(?:\.(?:0|[1-9][0-9]{0,2})){3}\Z', value):
        raise ValueError('Physical discovery requires an explicit private IPv4 address')
    octets = [int(part) for part in value.split('.')]
    if any(part > 255 for part in octets):
        raise ValueError('Invalid physical IPv4 address')
    private = octets[0] == 10 or (octets[0] == 172 and 16 <= octets[1] <= 31) or octets[:2] == [192, 168]
    if not private or octets[3] in (0, 255):
        raise ValueError('Physical discovery is limited to a private unicast IPv4 address')
    return value


def configured_address():
    return allowed_address(os.environ.get('INVT_MCP_PHYSICAL_ADDRESS'))


def gateway_record(gateway):
    return {'guid': text(gateway.guid), 'name': text(gateway.name)}


def scan_record(item):
    identity = item.device_id
    return {'address': text(item.address), 'device_name': text(item.device_name),
            'type_name': text(item.type_name), 'vendor_name': text(item.vendor_name),
            'device_identification': {'type': int(identity.type), 'id': text(identity.id), 'version': text(identity.version)},
            'block_driver': text(item.block_driver), 'block_driver_address': text(item.block_driver_address),
            'version_kind': 'device compatibility identification; not measured firmware version'}


def perform(request):
    address = configured_address()
    operation = request['operation']
    if operation not in OPS:
        raise ValueError('Unsupported physical discovery operation')

    def action():
        gateways = list(se.online.gateways)
        result = {'ok': True, 'operation': operation, 'physical_address': address,
                  'runtime_scope': 'physical_discovery_read_only', 'physical_runtime_allowed': False,
                  'timestamp_unix_ms': int(time.time() * 1000)}
        if operation == 'plc_gateways':
            result['gateways'] = [gateway_record(gateway) for gateway in gateways]
            return result
        selected = [gateway for gateway in gateways if text(gateway.guid).lower() == request.get('gateway_guid', '').lower()]
        if len(selected) != 1:
            raise ValueError('Select exactly one configured gateway by GUID')
        gateway = selected[0]
        resolved = gateway.find_address_by_ip(address, 11740)
        if not resolved:
            raise RuntimeError('Gateway did not resolve the requested PLC address')
        resolved = text(resolved)
        cached = [scan_record(item) for item in gateway.get_cached_network_scan_result() if text(item.address) == resolved]
        if len(cached) > 1:
            raise RuntimeError('Ambiguous cached identity for the resolved PLC address')
        result.update(gateway=gateway_record(gateway), codesys_address=resolved,
                      target=cached[0] if cached else None, identity_available=bool(cached),
                      identity_source='gateway cache after targeted IP lookup',
                      login_performed=False, application_downloaded=False)
        return result
    return with_executor(action)
