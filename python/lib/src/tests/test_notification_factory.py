import unittest
import psutil
from safecor import NotificationFactory, DiskState


class TestNotificationFactory(unittest.TestCase):

    def test_create_notification_disk_state(self):
        payload = NotificationFactory.create_notification_disk_state("My disk", DiskState.CONNECTED)
        self.assertEqual(payload["disk"], "My disk")
        self.assertEqual(payload["state"], DiskState.CONNECTED.value)

        payload = NotificationFactory.create_notification_disk_state("My disk", DiskState.DISCONNECTED)
        self.assertEqual(payload["disk"], "My disk")
        self.assertEqual(payload["state"], DiskState.DISCONNECTED.value)

    def test_create_notification_new_file(self):
        payload = NotificationFactory.create_notification_new_file("My disk", "/path/of/file.txt", "abd4534dbc98756", "1234567890")
        self.assertEqual(payload["disk"], "My disk")
        self.assertEqual(payload["filepath"], "/path/of/file.txt")
        self.assertEqual(payload["source_fingerprint"], "abd4534dbc98756")
        self.assertEqual(payload["dest_fingerprint"], "1234567890")

    def test_create_notification_error(self):
        payload = NotificationFactory.create_notification_error("My disk", "/path/of/file.bin", "There was an error")
        self.assertEqual(payload["disk"], "My disk")
        self.assertEqual(payload["filepath"], "/path/of/file.bin")
        self.assertEqual(payload["error"], "There was an error")

    def test_create_notification_energy_state(self):
        battery = psutil.sensors_battery()
        payload = NotificationFactory.create_notification_energy_state(battery)
        self.assertEqual(payload["battery_level"], battery.percent)
        self.assertEqual(payload["plugged"], battery.power_plugged)