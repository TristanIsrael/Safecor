import unittest

from safecor import ApiHelper, DiskState


class TestApiHelper(unittest.TestCase):
    def test_get_disk_name(self):
        disk_payload = {"disk": "My Disk", "state": "connected"}
        self.assertEqual(ApiHelper.get_disk_name(disk_payload), "My Disk")

    def test_get_disk_state(self):
        disk_payload = {"disk": "My Disk", "state": "connected"}
        self.assertEqual(ApiHelper.get_disk_state(disk_payload), DiskState.CONNECTED)

        disk_payload = {"disk": "My Disk", "state": "disconnected"}
        self.assertEqual(ApiHelper.get_disk_state(disk_payload), DiskState.DISCONNECTED)

    def test_is_disk_connected(self):
        disk_payload = {"disk": "My Disk", "state": "connected"}
        self.assertTrue(ApiHelper.is_disk_connected(disk_payload))

        disk_payload = {"disk": "My Disk", "state": "disconnected"}
        self.assertFalse(ApiHelper.is_disk_connected(disk_payload))
