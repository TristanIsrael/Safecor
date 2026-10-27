import types
import unittest
import unittest.mock as mock

from safecor import Dom0Controller, Topics, Constants, Settings, ComponentState
import safecor._dom0_controller as _dom0


class TestDom0Controller(unittest.TestCase):

    def setUp(self):
        self._patchers = [
            mock.patch.object(_dom0, "Logger", mock.MagicMock()),
            mock.patch.object(_dom0, "FileHelper", mock.MagicMock()),
            mock.patch.object(_dom0, "System", mock.MagicMock()),
            mock.patch.object(_dom0, "topology", mock.MagicMock()),
            mock.patch.object(_dom0, "subprocess", mock.MagicMock()),
            mock.patch.object(_dom0, "time", mock.MagicMock()),
            mock.patch.object(_dom0, "psutil", mock.MagicMock()),
        ]
        for p in self._patchers:
            p.start()
        self.addCleanup(self._stop_all)

        self.filehelper = _dom0.FileHelper
        self.system = _dom0.System
        self.topology = _dom0.topology
        self.subprocess = _dom0.subprocess
        self.psutil = _dom0.psutil

        self.mqtt = mock.MagicMock()
        self.ctrl = Dom0Controller(self.mqtt)

    def _stop_all(self):
        for p in self._patchers:
            p.stop()

    # --- ping ------------------------------------------------------------

    def test_handle_ping(self):
        self.ctrl._Dom0Controller__handle_ping({"id": 1, "data": "d", "sent_at": 5})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.PING}/response", {"id": 1, "source": "Dom0", "data": "d", "sent_at": 5}
        )

    # --- list files ------------------------------------------------------

    def test_handle_list_files_repository(self):
        self.filehelper.get_files_list.return_value = [{"name": "a"}]
        self.ctrl._Dom0Controller__handle_list_files({"disk": Constants.STR_REPOSITORY})
        self.filehelper.get_files_list.assert_called_with(Constants.STR_REPOSITORY, True)
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.LIST_FILES}/response", {"disk": Constants.STR_REPOSITORY, "files": [{"name": "a"}]}
        )

    def test_handle_list_files_not_repository(self):
        self.ctrl._Dom0Controller__handle_list_files({"disk": "other"})
        self.mqtt.publish.assert_not_called()

    # --- file fingerprint ------------------------------------------------

    def test_handle_file_fingerprint(self):
        self.filehelper.calculate_fingerprint.return_value = "fp123"
        self.ctrl._Dom0Controller__handle_file_fingerprint(
            {"disk": Constants.STR_REPOSITORY, "filepath": "/a.txt"}
        )
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.FILE_FINGERPRINT}/response",
            {"filepath": "/a.txt", "disk": Constants.STR_REPOSITORY, "fingerprint": "fp123"}
        )

    def test_handle_file_fingerprint_missing_args(self):
        self.ctrl._Dom0Controller__handle_file_fingerprint({"disk": Constants.STR_REPOSITORY})
        self.mqtt.publish.assert_not_called()

    # --- shutdown --------------------------------------------------------

    def test_handle_shutdown(self):
        self.ctrl._Dom0Controller__handle_shutdown({})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.SHUTDOWN}/response", {"state": "accepted", "reason": ""}
        )
        self.subprocess.run.assert_called_once()

    def test_handle_shutdown_already_in_progress(self):
        self.ctrl._Dom0Controller__is_shutting_down = True
        self.ctrl._Dom0Controller__handle_shutdown({})
        self.mqtt.publish.assert_not_called()

    # --- restart domain --------------------------------------------------

    def test_handle_restart_domain_forced_success(self):
        self.subprocess.run.return_value.returncode = 0
        self.ctrl._Dom0Controller__handle_restart_domain({"domain_name": "sys-usb", "forced": True})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.RESTART_DOMAIN}/response",
            {"domain_name": "sys-usb", "state": "accepted", "reason": ""}
        )

    def test_handle_restart_domain_forced_failure(self):
        res = mock.MagicMock()
        res.returncode = 1
        res.stdout = "out-err"
        res.stderr = "err-err"
        self.subprocess.run.return_value = res
        self.ctrl._Dom0Controller__handle_restart_domain({"domain_name": "sys-usb", "forced": True})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.RESTART_DOMAIN}/response",
            {"domain_name": "sys-usb", "state": "refused", "reason": "out-err\nerr-err"}
        )

    def test_handle_restart_domain_missing_arg(self):
        self.ctrl._Dom0Controller__handle_restart_domain({})
        self.mqtt.publish.assert_not_called()

    # --- gui ready -------------------------------------------------------

    def test_handle_gui_ready(self):
        self.ctrl._Dom0Controller__handle_gui_ready({})
        self.subprocess.run.assert_called_once()

    # --- energy state ----------------------------------------------------

    def test_handle_energy_state_with_battery(self):
        battery = types.SimpleNamespace(percent=50.5, power_plugged=True)
        self.psutil.sensors_battery.return_value = battery
        self.ctrl._Dom0Controller__handle_energy_state()
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.ENERGY_STATE}/response", {"battery_level": 50.5, "plugged": 1}
        )

    def test_handle_energy_state_no_battery(self):
        self.psutil.sensors_battery.return_value = None
        self.ctrl._Dom0Controller__handle_energy_state()
        self.mqtt.publish.assert_not_called()

    # --- system info -----------------------------------------------------

    def test_handle_system_info(self):
        self.system.get_system_information.return_value = {"core": {"version": "1"}}
        self.ctrl._Dom0Controller__handle_system_info()
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.SYSTEM_INFO}/response", {"core": {"version": "1"}}
        )

    # --- delete file -----------------------------------------------------

    def test_handle_delete_file_success(self):
        self.filehelper.return_value.remove_file.return_value = True
        self.ctrl._Dom0Controller__handle_delete_file(
            {"disk": Constants.STR_REPOSITORY, "filepath": "/a.txt"}
        )
        self.mqtt.publish.assert_called_once_with(
            Topics.DELETED_FILE, {"disk": Constants.STR_REPOSITORY, "filepath": "/a.txt"}
        )

    def test_handle_delete_file_wrong_disk(self):
        self.ctrl._Dom0Controller__handle_delete_file({"disk": "other", "filepath": "/a.txt"})
        self.mqtt.publish.assert_not_called()

    def test_handle_delete_file_missing_args(self):
        self.ctrl._Dom0Controller__handle_delete_file({})
        self.mqtt.publish.assert_not_called()

    # --- discover components --------------------------------------------

    def test_handle_discover_components(self):
        self.ctrl._Dom0Controller__handle_discover_components()
        self.mqtt.publish.assert_called_once()
        topic, payload = self.mqtt.publish.call_args[0]
        self.assertEqual(topic, f"{Topics.DISCOVER_COMPONENTS}/response")
        comp = payload["components"][0]
        self.assertEqual(comp["id"], Constants.SAFECOR_SYSTEM_CONTROLLER)
        self.assertEqual(comp["state"], ComponentState.READY.value)

    # --- settings: languages --------------------------------------------

    def test_handle_settings_languages_list(self):
        self.topology.languages = ["en", "fr"]
        self.ctrl._Dom0Controller__handle_system_settings(f"{Topics.LIST_LANGUAGES}/request", {})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.LIST_LANGUAGES}/response", {"languages": ["en", "fr"]}
        )

    def test_handle_settings_default_language(self):
        self.topology.default_language = "fr"
        self.ctrl._Dom0Controller__handle_system_settings(f"{Topics.DEFAULT_LANGUAGE}/request", {})
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.DEFAULT_LANGUAGE}/response", {"language": "fr"}
        )

    def test_handle_settings_current_language(self):
        self.system.return_value.get_setting.return_value = "en"
        self.ctrl._Dom0Controller__handle_system_settings(
            f"{Topics.CURRENT_LANGUAGE}/get", {"key": Settings.CURRENT_LANGUAGE}
        )
        self.mqtt.publish.assert_called_once_with(
            f"{Topics.CURRENT_LANGUAGE}/response",
            {"key": Settings.CURRENT_LANGUAGE, "value": "en"}
        )

    def test_handle_settings_current_language_missing_key(self):
        self.ctrl._Dom0Controller__handle_system_settings(f"{Topics.CURRENT_LANGUAGE}/get", {})
        self.mqtt.publish.assert_not_called()

    def test_handle_settings_set_language(self):
        self.system.return_value.get_setting.return_value = "fr"  # different from requested "en"
        self.ctrl._Dom0Controller__handle_system_settings(
            f"{Topics.SET_LANGUAGE}/request",
            {"key": Settings.CURRENT_LANGUAGE, "value": "en"}
        )
        self.system.return_value.set_setting.assert_called_with(Settings.CURRENT_LANGUAGE, "en")
        # Two publishes: the setting response + the change notification
        self.assertEqual(self.mqtt.publish.call_count, 2)

    def test_handle_settings_set_language_unchanged(self):
        self.system.return_value.get_setting.return_value = "en"  # same as requested
        self.ctrl._Dom0Controller__handle_system_settings(
            f"{Topics.SET_LANGUAGE}/request",
            {"key": Settings.CURRENT_LANGUAGE, "value": "en"}
        )
        # Value did not change -> no response published
        self.mqtt.publish.assert_not_called()

    # --- switch gui ------------------------------------------------------

    def test_handle_switch_gui_missing_arg(self):
        self.ctrl._Dom0Controller__handle_switch_gui({})
        self.mqtt.publish.assert_not_called()

    def test_handle_switch_gui_not_found(self):
        with mock.patch.object(_dom0, "XcbController", create=True, new=mock.MagicMock()) as xcb:
            xcb.return_value.get_gui_list.return_value = {"other": 123}
            self.ctrl._Dom0Controller__handle_switch_gui({"domain": "sys-usb"})
        xcb.return_value.show_gui.assert_not_called()

    def test_handle_switch_gui_success(self):
        with mock.patch.object(_dom0, "XcbController", create=True, new=mock.MagicMock()) as xcb:
            xcb.return_value.get_gui_list.return_value = {"sys-usb": 42}
            xcb.return_value.get_current_gui.return_value = ("old", 7)
            self.ctrl._Dom0Controller__handle_switch_gui({"domain": "sys-usb"})
        xcb.return_value.hide_gui.assert_called_once_with(7)
        xcb.return_value.show_gui.assert_called_once_with(42)

    # --- dispatcher ------------------------------------------------------

    def test_message_worker_dispatch_ping(self):
        self.ctrl._Dom0Controller__message_worker(
            f"{Topics.PING}/request", {"id": 9, "data": "x", "sent_at": 1}
        )
        self.mqtt.publish.assert_called_once()

    def test_message_worker_unknown_topic(self):
        # An unknown topic must not raise nor publish
        self.ctrl._Dom0Controller__message_worker("some/unknown/topic", {})
        self.mqtt.publish.assert_not_called()

    # --- on connected ----------------------------------------------------

    def test_on_mqtt_connected_subscribes(self):
        self.system.return_value.parse_kernel_command_line_settings.return_value = {}
        self.topology.default_language = "en"
        self.ctrl._Dom0Controller__on_mqtt_connected()
        self.assertGreaterEqual(self.mqtt.subscribe.call_count, 10)
        self.system.return_value.set_setting.assert_called()


if __name__ == "__main__":
    unittest.main()
