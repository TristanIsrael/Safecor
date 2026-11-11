"""Unit tests for DirectMountManager.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import unittest
from unittest.mock import MagicMock, patch

from safecor import Constants, DirectMountManager


class TestDirectMountManager(unittest.TestCase):
    def setUp(self):
        self.manager = DirectMountManager()
        # Reset class-level state
        DirectMountManager._DirectMountManager__mounted = False
        DirectMountManager._DirectMountManager__sshfs_process = None
        DirectMountManager._DirectMountManager__mount_mode = "rw"

    def tearDown(self):
        DirectMountManager._DirectMountManager__mounted = False
        DirectMountManager._DirectMountManager__sshfs_process = None
        DirectMountManager._DirectMountManager__mount_mode = "rw"

    def test_get_mount_point(self):
        self.assertEqual(self.manager.get_mount_point(), Constants.USB_MOUNT_POINT)

    def test_is_mounted_initially_false(self):
        self.assertFalse(self.manager.is_mounted())

    def test_start_returns_false_when_no_direct_mount(self):
        with patch.object(
            DirectMountManager,
            "_DirectMountManager__query_direct_mount_config",
            return_value=None,
        ):
            result = self.manager.start()
            self.assertFalse(result)
            self.assertFalse(self.manager.is_mounted())

    def test_start_returns_false_when_domid_not_found(self):
        with (
            patch.object(
                DirectMountManager,
                "_DirectMountManager__query_direct_mount_config",
                return_value="rw",
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__wait_for_domid",
                return_value=None,
            ),
        ):
            result = self.manager.start()
            self.assertFalse(result)
            self.assertFalse(self.manager.is_mounted())

    def test_start_returns_false_when_vchan_script_fails(self):
        with (
            patch.object(
                DirectMountManager,
                "_DirectMountManager__query_direct_mount_config",
                return_value="rw",
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__wait_for_domid",
                return_value=5,
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__generate_vchan_script",
                return_value=False,
            ),
        ):
            result = self.manager.start()
            self.assertFalse(result)

    def test_start_returns_false_when_mount_fails(self):
        with (
            patch.object(
                DirectMountManager,
                "_DirectMountManager__query_direct_mount_config",
                return_value="rw",
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__wait_for_domid",
                return_value=5,
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__generate_vchan_script",
                return_value=True,
            ),
            patch.object(
                DirectMountManager, "_DirectMountManager__mount", return_value=False
            ),
        ):
            result = self.manager.start()
            self.assertFalse(result)

    def test_start_success(self):
        with (
            patch.object(
                DirectMountManager,
                "_DirectMountManager__query_direct_mount_config",
                return_value="rw",
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__wait_for_domid",
                return_value=5,
            ),
            patch.object(
                DirectMountManager,
                "_DirectMountManager__generate_vchan_script",
                return_value=True,
            ),
            patch.object(
                DirectMountManager, "_DirectMountManager__mount", return_value=True
            ),
        ):
            result = self.manager.start()
            self.assertTrue(result)
            self.assertTrue(self.manager.is_mounted())

    def test_stop_when_not_mounted(self):
        # Should not raise
        self.manager.stop()
        self.assertFalse(self.manager.is_mounted())

    def test_stop_when_mounted(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        DirectMountManager._DirectMountManager__sshfs_process = mock_proc
        DirectMountManager._DirectMountManager__mounted = True

        with patch("subprocess.run"):
            self.manager.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()
        self.assertFalse(self.manager.is_mounted())

    def test_generate_vchan_script(self):
        with (
            patch("builtins.open", return_value=MagicMock()),
            patch("os.makedirs"),
            patch("os.chmod") as mock_chmod,
        ):
            result = self.manager._DirectMountManager__generate_vchan_script(5)
            self.assertTrue(result)
            mock_chmod.assert_called_once()

    def test_generate_vchan_script_os_error(self):
        with patch("builtins.open", side_effect=OSError("test")):
            result = self.manager._DirectMountManager__generate_vchan_script(5)
            self.assertFalse(result)

    def test_wait_for_domid_found_immediately(self):
        with patch("safecor._direct_mount_manager.System") as mock_system:
            mock_system.return_value.get_domain_domid.return_value = 12
            result = self.manager._DirectMountManager__wait_for_domid("sys-usb")
            self.assertEqual(result, 12)

    def test_wait_for_domid_timeout(self):
        with (
            patch("safecor._direct_mount_manager.System") as mock_system,
            patch("safecor._direct_mount_manager.time") as mock_time,
        ):
            mock_system.return_value.get_domain_domid.return_value = None
            mock_time.time.side_effect = [0, 1, 2, 100]
            mock_time.sleep = MagicMock()
            result = self.manager._DirectMountManager__wait_for_domid("sys-usb")
            self.assertIsNone(result)

    def test_query_direct_mount_config_no_response(self):
        with patch("safecor._direct_mount_manager.MqttFactory") as mock_factory:
            mock_helper = MagicMock()
            mock_helper.send_request.return_value = None
            mock_factory.return_value.get_api_helper.return_value = mock_helper
            result = self.manager._DirectMountManager__query_direct_mount_config()
            self.assertIsNone(result)

    def test_query_direct_mount_config_with_response(self):
        with (
            patch("safecor._direct_mount_manager.System") as mock_system,
            patch("safecor._direct_mount_manager.MqttFactory") as mock_factory,
        ):
            mock_system.domain_name.return_value = "test-domain"
            mock_helper = MagicMock()
            mock_helper.send_request.return_value = {
                "domains": [
                    {"name": "other", "direct_mount": None},
                    {"name": "test-domain", "direct_mount": {"mode": "ro"}},
                ]
            }
            mock_factory.return_value.get_api_helper.return_value = mock_helper
            result = self.manager._DirectMountManager__query_direct_mount_config()
            self.assertEqual(result, "ro")

    def test_mount_mode_ro(self):
        DirectMountManager._DirectMountManager__mount_mode = "ro"
        with (
            patch("subprocess.Popen") as mock_popen,
            patch("safecor._direct_mount_manager.time.sleep"),
            patch("os.makedirs"),
        ):
            mock_popen.return_value.poll.return_value = None
            self.manager._DirectMountManager__mount()
            call_args = mock_popen.call_args[0][0]
            opts_idx = call_args.index("-o")
            opts = call_args[opts_idx + 1]
            self.assertIn("ro", opts)


if __name__ == "__main__":
    unittest.main()
