import base64
import unittest
import unittest.mock as mock
from paho.mqtt.enums import MQTTErrorCode

from safecor import Api, Topics, Constants
import safecor._api as _api


class TestApi(unittest.TestCase):

    def setUp(self):
        api = Api()
        # Reset singleton state (class-level callback lists and subscriptions)
        api._Api__message_callbacks.clear()
        api._Api__ready_callbacks.clear()
        api._Api__subscription_callbacks.clear()
        api._Api__shutdown_callbacks.clear()
        api._Api__restart_callbacks.clear()
        api._Api__subscriptions.clear()

        self._patchers = [
            mock.patch.object(_api, "Logger", mock.MagicMock()),
            mock.patch.object(_api, "System", mock.MagicMock()),
        ]
        for p in self._patchers:
            p.start()
        self.addCleanup(self._stop_all)
        _api.System.domain_name.return_value = "testdomain"

        self.mqtt = mock.MagicMock()
        self.api = api
        self.api.start(self.mqtt)

    def _stop_all(self):
        for p in self._patchers:
            p.stop()

    # --- lifecycle -------------------------------------------------------

    def test_start_and_get_client(self):
        self.mqtt.start.assert_called_once()
        self.assertIs(self.api.get_mqtt_client(), self.mqtt)

    def test_stop(self):
        self.api.stop()
        self.mqtt.stop.assert_called_once()

    # --- callback registration -------------------------------------------

    def test_add_message_callback(self):
        cb = lambda t, p: None
        self.api.add_message_callback(cb)
        self.api.add_message_callback(cb)  # dedupe
        self.assertEqual(self.api._Api__message_callbacks.count(cb), 1)

    def test_add_message_callback_none(self):
        self.api.add_message_callback(None)  # should not raise
        self.assertEqual(self.api._Api__message_callbacks, [])

    def test_add_ready_callback(self):
        cb = lambda: None
        self.api.add_ready_callback(cb)
        self.assertIn(cb, self.api._Api__ready_callbacks)

    def test_add_subscription_callback(self):
        cb = lambda mid: None
        self.api.add_subscription_callback(cb)
        self.assertIn(cb, self.api._Api__subscription_callbacks)

    def test_add_shutdown_and_restart_callbacks(self):
        self.api.add_shutdown_callback(lambda s, r: None)
        self.api.add_restart_callback(lambda d, s, r: None)
        self.assertEqual(len(self.api._Api__shutdown_callbacks), 1)
        self.assertEqual(len(self.api._Api__restart_callbacks), 1)

    # --- subscribe / publish ---------------------------------------------

    def test_subscribe_success(self):
        self.mqtt.subscribe.return_value = (MQTTErrorCode.MQTT_ERR_SUCCESS, 5)
        self.assertEqual(self.api.subscribe("topic"), (True, 5))

    def test_subscribe_error(self):
        # Any non-zero code is treated as an error (SUCCESS == 0)
        self.mqtt.subscribe.return_value = (1, None)
        self.assertEqual(self.api.subscribe("topic"), (False, None))

    def test_subscribe_duplicate_returns_none(self):
        # The topic is already tracked -> returns None without calling the client
        self.api._Api__subscriptions.append("topic")
        self.assertIsNone(self.api.subscribe("topic"))
        self.mqtt.subscribe.assert_not_called()

    def test_publish(self):
        self.api.publish("some/topic", {"a": 1})
        self.mqtt.publish.assert_called_once_with("some/topic", {"a": 1})

    # --- logging passthrough ---------------------------------------------

    def test_log_methods(self):
        self.api.debug("d")
        self.api.info("i")
        self.api.warn("w")
        self.api.error("e")
        self.api.critical("c")
        logger = _api.Logger.return_value
        logger.debug.assert_called_once()
        logger.info.assert_called_once()
        logger.warn.assert_called_once()
        logger.error.assert_called_once()
        logger.critical.assert_called_once()

    # --- storage commands ------------------------------------------------

    def test_get_disks_list(self):
        self.api.get_disks_list()
        self.mqtt.publish.assert_called_once_with(f"{Topics.LIST_DISKS}/request", {})

    def test_get_files_list(self):
        self.api.get_files_list("disk1", True, "/sub", ["*.txt"])
        self.mqtt.publish.assert_called_once()
        topic, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(topic, f"{Topics.LIST_FILES}/request")
        self.assertEqual(payload["disk"], "disk1")
        self.assertEqual(payload["recursive"], True)

    def test_read_file(self):
        self.api.read_file("disk1", "/a.txt")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.READ_FILE}/request", {"disk": "disk1", "filepath": "/a.txt"}
        )

    def test_copy_file(self):
        self.api.copy_file("disk1", "/a.txt", "disk2")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.COPY_FILE}/request",
            {"disk": "disk1", "filepath": "/a.txt", "destination": "disk2"}
        )

    def test_delete_file(self):
        self.api.delete_file("/a.txt", "disk1")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.DELETE_FILE}/request", {"filepath": "/a.txt", "disk": "disk1"}
        )

    def test_get_file_fingerprint(self):
        self.api.get_file_fingerprint("/a.txt", "disk1")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.FILE_FINGERPRINT}/request", {"filepath": "/a.txt", "disk": "disk1"}
        )

    def test_create_file(self):
        self.api.create_file("/a.txt", "disk1", b"hello")
        self.mqtt.publish.assert_called_once()
        topic, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(topic, f"{Topics.CREATE_FILE}/request")
        self.assertEqual(payload["data"], base64.b64encode(b"hello").decode("utf-8"))

    def test_create_file_binary(self):
        self.api.create_file("/a.bin", "disk1", b"\x00\x01", binary=True)
        self.mqtt.publish.assert_called_once()
        _, payload = self.mqtt.publish.call_args[0]
        self.assertTrue(payload["compressed"])

    def test_mount_file(self):
        self.api.mount_file("disk1", "/a.iso")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.MOUNT_FILE}/request", {"disk": "disk1", "filepath": "/a.iso"}
        )

    def test_archive_extensions_handled(self):
        self.assertEqual(self.api.archive_extensions_handled(), Constants.ARCHIVE_EXTENSIONS_HANDLED)

    def test_unmount(self):
        self.api.unmount("disk1")
        self.mqtt.publish.assert_called_once_with(f"{Topics.UNMOUNT}/request", {"disk": "disk1"})

    # --- discovery / info / energy ---------------------------------------

    def test_discover_components(self):
        self.api.discover_components()
        self.mqtt.publish.assert_called_once_with(f"{Topics.DISCOVER_COMPONENTS}/request", {})

    def test_publish_components(self):
        self.api.publish_components([{"id": "x"}])
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.DISCOVER_COMPONENTS}/response", {"components": [{"id": "x"}]}
        )

    def test_request_energy_state(self):
        self.api.request_energy_state()
        self.mqtt.publish.assert_called_once_with(f"{Topics.ENERGY_STATE}/request", {})

    def test_request_system_info(self):
        self.api.request_system_info()
        self.mqtt.publish.assert_called_once_with(f"{Topics.SYSTEM_INFO}/request", {})

    def test_clear_sys_usb_queues(self):
        self.api.clear_sys_usb_queues()
        self.mqtt.publish.assert_called_once_with(f"{Topics.SYS_USB_CLEAR_QUEUES}/request", {})

    # --- settings / languages --------------------------------------------

    def test_get_languages_list(self):
        self.api.get_languages_list()
        self.mqtt.publish.assert_called_once_with(f"{Topics.LANGUAGES}/request", {})

    def test_get_default_language(self):
        self.api.get_default_language()
        self.mqtt.publish.assert_called_once_with(f"{Topics.DEFAULT_LANGUAGE}/request", {})

    def test_get_current_language(self):
        self.api.get_current_language()
        self.mqtt.publish.assert_called_once_with(f"{Topics.CURRENT_LANGUAGE}/request", {})

    def test_set_current_language(self):
        self.api.set_current_language("fr")
        self.mqtt.publish.assert_called_once_with(f"{Topics.SET_LANGUAGE}/request", {"language": "fr"})

    # --- notifications ---------------------------------------------------

    def test_notify_disk_added(self):
        self.api.notify_disk_added("disk1")
        self.mqtt.publish.assert_called_once_with(
            Topics.DISK_STATE, {"disk": "disk1", "state": "connected"}
        )

    def test_notify_disk_removed(self):
        self.api.notify_disk_removed("disk1")
        self.mqtt.publish.assert_called_once_with(
            Topics.DISK_STATE, {"disk": "disk1", "state": "disconnected"}
        )

    def test_notify_gui_ready(self):
        self.api.notify_gui_ready()
        self.mqtt.publish.assert_called_once_with(Topics.GUI_READY, {})

    # --- workflow --------------------------------------------------------

    def test_shutdown(self):
        self.api.shutdown()
        self.mqtt.publish.assert_called_once_with(f"{Topics.SHUTDOWN}/request", {})

    def test_restart_domain(self):
        self.api.restart_domain("sys-usb")
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.RESTART_DOMAIN}/request", {"domain_name": "sys-usb"}
        )

    def test_switch_gui(self):
        self.api.switch_gui("sys-gui")
        self.mqtt.publish.assert_called_once_with(f"{Topics.SWITCH_GUI}/request", {"domain": "sys-gui"})

    def test_ping(self):
        self.api.ping("target", "data")
        self.mqtt.publish.assert_called_once()
        topic, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(topic, f"{Topics.PING}/target/request")
        self.assertEqual(payload["source"], "testdomain")
        self.assertEqual(payload["data"], "data")

    # --- private event handlers ------------------------------------------

    def test_on_message_received_normal(self):
        received = []
        self.api.add_message_callback(lambda t, p: received.append((t, p)))
        self.api._Api__on_message_received("some/topic", {"a": 1})
        self.assertEqual(received, [("some/topic", {"a": 1})])

    def test_on_message_received_shutdown(self):
        received = []
        self.api.add_shutdown_callback(lambda s, r: received.append((s, r)))
        self.api._Api__on_message_received(f"{Topics.SHUTDOWN}/response", {"state": "accepted", "reason": ""})
        self.assertEqual(received, [(True, "")])

    def test_on_message_received_restart(self):
        received = []
        self.api.add_restart_callback(lambda d, s, r: received.append((d, s, r)))
        self.api._Api__on_message_received(
            f"{Topics.RESTART_DOMAIN}/response", {"domain_name": "sys-usb", "state": "refused", "reason": "x"}
        )
        self.assertEqual(received, [("sys-usb", False, "x")])

    def test_on_message_received_ping_request(self):
        self.api._Api__on_message_received(
            f"{Topics.PING}/testdomain/request", {"id": 1, "data": "d", "sent_at": 5}
        )
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.PING}/testdomain/response",
            {"id": 1, "source": "testdomain", "data": "d", "sent_at": 5}
        )

    def test_on_message_received_callback_exception(self):
        def bad_cb(t, p):
            raise ValueError("boom")
        self.api.add_message_callback(bad_cb)
        # Must not propagate
        self.api._Api__on_message_received("some/topic", {})

    def test_on_subscribed(self):
        received = []
        self.api.add_subscription_callback(lambda mid: received.append(mid))
        self.api._Api__on_subscribed(3)
        self.assertEqual(received, [3])

    def test_on_mqtt_connected(self):
        received = []
        self.api.add_ready_callback(lambda: received.append("ready"))
        self.mqtt.subscribe.return_value = (MQTTErrorCode.MQTT_ERR_SUCCESS, 1)
        self.api._Api__on_mqtt_connected()
        self.assertEqual(received, ["ready"])
        self.assertGreaterEqual(self.mqtt.subscribe.call_count, 3)


if __name__ == "__main__":
    unittest.main()
