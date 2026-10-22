import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'src/scripts/invt_hardware.py'
fake_engine = SimpleNamespace(online=SimpleNamespace(gateways=[]))
with patch.dict(sys.modules, scriptengine=fake_engine,
                invt_executor=SimpleNamespace(with_executor=lambda action: action())):
    spec = importlib.util.spec_from_file_location('hardware_under_test', SCRIPT)
    hardware = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hardware)


class Gateway:
    guid = '11111111-1111-4111-8111-111111111111'
    name = 'USB test gateway'

    def __init__(self, cached=()):
        self.cached = cached
        self.calls = []

    def find_address_by_ip(self, address, port):
        self.calls.append((address, port))
        return '[0001]'

    def get_cached_network_scan_result(self):
        return self.cached

    def perform_network_scan(self):
        raise AssertionError('Broad network scan must never be invoked')


def target(address='[0001]'):
    return SimpleNamespace(address=address, device_name='Bench PLC', type_name='TM751',
                           vendor_name='INVT', device_id=SimpleNamespace(type=4102, id='test-only', version='test-only'),
                           block_driver='Tcp', block_driver_address='192.168.3.10:11740')


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, INVT_MCP_PHYSICAL_ADDRESS='192.168.3.10')
        self.environment.start()
        self.addCleanup(self.environment.stop)
        fake_engine.online.gateways = []

    def test_opt_in_required_before_gateway_access(self):
        with patch.dict(os.environ, INVT_MCP_PHYSICAL_ADDRESS=''):
            with self.assertRaises(ValueError):
                hardware.perform({'operation': 'plc_gateways'})

    def test_private_address_validation(self):
        for value in ('localhost', '127.0.0.1', '8.8.8.8', '224.0.0.1', '192.168.3.0',
                      '192.168.3.255', '192.168.3.256', '192.168.03.10', '192.168.3.10\n', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hardware.allowed_address(value)
        self.assertEqual(hardware.allowed_address('192.168.3.10'), '192.168.3.10')

    def test_gateway_listing_does_not_probe(self):
        gateway = Gateway()
        fake_engine.online.gateways = [gateway]
        result = hardware.perform({'operation': 'plc_gateways'})
        self.assertEqual(result['gateways'][0]['guid'], gateway.guid)
        self.assertEqual(gateway.calls, [])
        self.assertFalse(result['physical_runtime_allowed'])

    def test_targeted_lookup_and_matching_identity(self):
        gateway = Gateway([target('[unrelated]'), target()])
        fake_engine.online.gateways = [gateway]
        result = hardware.perform({'operation': 'plc_find', 'gateway_guid': gateway.guid})
        self.assertEqual(gateway.calls, [('192.168.3.10', 11740)])
        self.assertEqual(result['target']['type_name'], 'TM751')
        self.assertTrue(result['identity_available'])
        self.assertFalse(result['login_performed'])
        self.assertFalse(result['application_downloaded'])

    def test_no_first_gateway_fallback(self):
        gateway = Gateway()
        fake_engine.online.gateways = [gateway]
        with self.assertRaises(ValueError):
            hardware.perform({'operation': 'plc_find', 'gateway_guid': 'stale'})
        self.assertEqual(gateway.calls, [])

    def test_absent_identity_is_reported_not_invented(self):
        gateway = Gateway([target('[another]')])
        fake_engine.online.gateways = [gateway]
        result = hardware.perform({'operation': 'plc_find', 'gateway_guid': gateway.guid})
        self.assertFalse(result['identity_available'])
        self.assertIsNone(result['target'])

    def test_duplicate_cached_identity_is_refused(self):
        gateway = Gateway([target(), target()])
        fake_engine.online.gateways = [gateway]
        with self.assertRaises(RuntimeError):
            hardware.perform({'operation': 'plc_find', 'gateway_guid': gateway.guid})

    def test_empty_resolution_does_not_become_a_string_identity(self):
        gateway = Gateway()
        gateway.find_address_by_ip = lambda address, port: None
        fake_engine.online.gateways = [gateway]
        with self.assertRaises(RuntimeError):
            hardware.perform({'operation': 'plc_find', 'gateway_guid': gateway.guid})


if __name__ == '__main__':
    unittest.main()
