import unittest
import types
from safecor import NotificationFactory, DiskState


def make_battery(percent, plugged):
    return types.SimpleNamespace(percent=percent, power_plugged=plugged)


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

    def test_create_notification_energy_state_plugged(self):
        payload = NotificationFactory.create_notification_energy_state(make_battery(76.234, True))
        self.assertEqual(payload["battery_level"], 76.23)
        self.assertEqual(payload["plugged"], 1)

    def test_create_notification_energy_state_unplugged(self):
        payload = NotificationFactory.create_notification_energy_state(make_battery(100.0, False))
        self.assertEqual(payload["battery_level"], 100.0)
        self.assertEqual(payload["plugged"], 0)

    def test_create_notification_deleted_file(self):
        payload = NotificationFactory.create_notification_deleted_file("My disk", "/path/of/file.txt")
        self.assertEqual(payload, {"disk": "My disk", "filepath": "/path/of/file.txt"})

    def test_create_notification_setting_changed(self):
        payload = NotificationFactory.create_notification_setting_changed("default_language", "fr")
        self.assertEqual(payload, {"key": "default_language", "value": "fr"})


if __name__ == "__main__":
    unittest.main()
