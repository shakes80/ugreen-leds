"""Hardware-free policy and protocol regression tests."""
import copy
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('ugreen_leds', str(ROOT / 'src/ugreen-leds'))
spec = importlib.util.spec_from_loader(loader.name, loader)
leds = importlib.util.module_from_spec(spec)
loader.exec_module(leds)

CONFIG = {'brightness': 255, 'bays': {'disk1': 1, 'disk2': 2}}


def healthy_pools():
    return {'pools': {
        'rpool': {'state': 'ONLINE', 'error_count': '0', 'vdevs': {}},
        'datapool': {'state': 'ONLINE', 'error_count': '0', 'vdevs': {
            'datapool': {'state': 'ONLINE', 'vdevs': {
                'drive': {'state': 'ONLINE', 'phys_path': 'pci-0000:00:17.0-ata-2.0',
                          'read_errors': '0', 'write_errors': '0', 'checksum_errors': '0'}
            }}
        }}
    }}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.health = leds.zfs_health(healthy_pools(), ['rpool', 'datapool'])

    def test_empty_and_present_bays(self):
        result = leds.policy(CONFIG, self.health, {2: {}}, True, set())
        self.assertEqual(result['power']['mode'], 1)
        self.assertEqual(result['power']['rgb'], leds.WHITE)
        self.assertEqual(result['disk1']['mode'], 0)
        self.assertEqual(result['disk2']['mode'], 1)

    def test_network_and_disk_activity_blink(self):
        result = leds.policy(CONFIG, self.health, {2: {}}, True, {'disk2', 'netdev'})
        self.assertEqual(result['netdev']['mode'], 2)
        self.assertEqual(result['disk2']['mode'], 2)
        self.assertEqual(result['disk1']['mode'], 0)

    def test_link_down_is_amber(self):
        result = leds.policy(CONFIG, self.health, {2: {}}, False, set())
        self.assertEqual(result['netdev']['rgb'], leds.AMBER)
        self.assertEqual(result['netdev']['mode'], 1)

    def test_missing_faulted_drive_keeps_fault_indicator(self):
        data = healthy_pools()
        data['pools']['datapool']['state'] = 'DEGRADED'
        data['pools']['datapool']['vdevs']['datapool']['vdevs']['drive']['state'] = 'FAULTED'
        health = leds.zfs_health(data, ['rpool', 'datapool'])
        result = leds.policy(CONFIG, health, {}, True, set())
        self.assertFalse(health['healthy'])
        self.assertEqual(health['bad_bays'], [2])
        self.assertEqual(result['power']['rgb'], leds.AMBER)
        self.assertEqual(result['disk2']['rgb'], leds.AMBER)
        self.assertEqual(result['disk2']['mode'], 2)

    def test_online_drive_with_errors_is_not_healthy(self):
        data = healthy_pools()
        data['pools']['datapool']['vdevs']['datapool']['vdevs']['drive']['checksum_errors'] = '1'
        health = leds.zfs_health(data, ['rpool', 'datapool'])
        self.assertFalse(health['healthy'])
        self.assertEqual(health['bad_bays'], [2])

    def test_missing_expected_pool_is_not_healthy(self):
        data = healthy_pools()
        del data['pools']['datapool']
        self.assertFalse(leds.zfs_health(data, ['rpool', 'datapool'])['healthy'])
        self.assertFalse(leds.zfs_health({'pools': {}}, ['rpool', 'datapool'])['healthy'])

    def test_ata_mapping_does_not_include_usb_devices(self):
        self.assertEqual(leds.bay_number('/sys/devices/pci0000:00/ata2/host1/block/sda'), 2)
        self.assertEqual(leds.bay_number('pci-0000:00:17.0-ata-2.0'), 2)
        self.assertIsNone(leds.bay_number('/sys/devices/usb1/block/sdb'))


class FakeBus:
    def __init__(self):
        # Valid protocol response: on, full white, 256 ms on / 512 ms off.
        self.response = [1, 255, 255, 255, 255, 3, 0, 1, 0, 4, 1]
        self.replies = []
        self.writes = []
        self.ack = 1

    def read_i2c_block_data(self, address, register, length):
        if address != 0x3a or length != 11:
            raise AssertionError('Unexpected controller read')
        return self.replies.pop(0) if self.replies else list(self.response)

    def write_i2c_block_data(self, address, register, payload):
        self.writes.append((address, register, list(payload)))

    def read_byte_data(self, address, register):
        if address != 0x3a or register != 0x80:
            raise AssertionError('Unexpected acknowledgment register')
        return self.ack


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.controller = leds.Controller.__new__(leds.Controller)
        self.controller.bus = FakeBus()
        self.controller.cached = {}
        self.lock = tempfile.TemporaryFile()
        self.controller.lock = self.lock
        self.sleep = patch.object(leds.time, 'sleep')
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.lock.close()

    def test_multiple_reads_preserve_lock_and_decode_timing(self):
        for name in ['power', 'netdev']:
            state = self.controller.read(name)
            self.assertEqual(state['rgb'], leds.WHITE)
            self.assertEqual((state['on_ms'], state['off_ms']), (256, 512))
        self.assertFalse(self.lock.closed)

    def test_bad_checksum_is_retried_then_validated(self):
        bad = copy.copy(self.controller.bus.response)
        bad[-1] ^= 1
        self.controller.bus.replies = [bad, self.controller.bus.response]
        self.assertEqual(self.controller.read('power')['mode'], 1)
        self.controller.bus.replies = [bad] * 5
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            self.controller.read('power')

    def test_command_matches_upstream_packet_vector(self):
        self.controller.write('disk2', 0x02, [255, 255, 255])
        self.assertEqual(self.controller.bus.writes[-1],
                         (0x3a, 3, [3, 160, 1, 0, 0, 2, 255, 255, 255, 0, 3, 160]))

    def test_missing_acknowledgment_is_an_error(self):
        self.controller.bus.ack = 0
        with self.assertRaisesRegex(RuntimeError, 'acknowledged'):
            self.controller.apply('power', leds.led_state())
        self.assertNotIn('power', self.controller.cached)

    def test_unchanged_state_does_not_repeat_commands(self):
        state = leds.led_state(mode=2)
        self.controller.apply('disk2', state)
        count = len(self.controller.bus.writes)
        self.controller.apply('disk2', state)
        self.assertEqual(len(self.controller.bus.writes), count)


if __name__ == '__main__':
    unittest.main()
