"""Unit tests for SysUsbController.

Covers the SFTP channel logic of the direct USB mount (the module-level
functions integrated from the former safecor-vchan-sftp script) and the
``safecor_direct_mount`` component state machine.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from safecor import ComponentState, Constants, MountMode, Topics
from safecor import _sys_usb_controller as suc
from safecor._sys_usb_controller import SysUsbController

MANGLED = "_SysUsbController"


def make_context():
    """A sandbox context with the Alpine 3.24 values."""
    return suc.SandboxContext(
        setpriv="/bin/setpriv",
        setpriv_libs=["/usr/lib/libeconf.so.0", "/usr/lib/libcap-ng.so.0"],
        passwd=suc.SANDBOX_PASSWD,
    )


class TestSftpChannelFunctions(unittest.TestCase):
    """The SFTP channel logic (module-level functions of the controller)."""

    def test_constants(self):
        self.assertEqual(suc.SFTP_ROOT, "/media/usb")
        self.assertEqual(suc.SFTP_SERVER, "/usr/lib/ssh/sftp-server")
        self.assertEqual(suc.MUSL_LOADER, "/lib/ld-musl-x86_64.so.1")
        self.assertEqual(suc.SFTP_USER, "svc-sys-usb-sftp")
        self.assertEqual(suc.SFTP_RUNTIME_DIR, "/var/run/safecor/direct-mount")
        self.assertEqual(
            suc.SANDBOX_PASSWD,
            "/var/run/safecor/direct-mount/sftp-sandbox-passwd",
        )
        self.assertEqual(
            suc.DM_CHANNELS_HELPER, "/usr/lib/safecor/bin/safecor-dm-channels.py"
        )

    def test_parse_direct_mount_domains(self):
        response = {
            "domains": [
                {"name": "sys-usb", "direct_mount": False},
                {"name": "app1", "direct_mount": {"mode": "ro"}},
                {"name": "app2", "direct_mount": {"mode": "rw"}},
            ]
        }
        self.assertEqual(
            suc.parse_direct_mount_domains(response),
            [("app1", MountMode.RO), ("app2", MountMode.RW)],
        )

    def test_parse_direct_mount_domains_falsy_is_disabled(self):
        # A falsy direct_mount (False, None, {}) is "not enabled", as in the
        # DirectMountManager reference implementation.
        response = {
            "domains": [
                {"name": "app1", "direct_mount": {}},
                {"name": "app2", "direct_mount": None},
            ]
        }
        self.assertEqual(suc.parse_direct_mount_domains(response), [])

    def test_parse_direct_mount_domains_invalid_mode_defaults_to_rw(self):
        response = {"domains": [{"name": "app1", "direct_mount": {"mode": "weird"}}]}
        self.assertEqual(
            suc.parse_direct_mount_domains(response), [("app1", MountMode.RW)]
        )

    def test_parse_direct_mount_domains_non_dict_defaults_to_rw(self):
        response = {"domains": [{"name": "app1", "direct_mount": True}]}
        self.assertEqual(
            suc.parse_direct_mount_domains(response), [("app1", MountMode.RW)]
        )

    def test_parse_direct_mount_domains_empty(self):
        self.assertEqual(suc.parse_direct_mount_domains({}), [])
        self.assertEqual(suc.parse_direct_mount_domains({"domains": []}), [])

    def test_sftp_server_args_rw(self):
        self.assertEqual(suc.sftp_server_args(MountMode.RW), ["-u", "077"])

    def test_sftp_server_args_ro(self):
        self.assertEqual(suc.sftp_server_args(MountMode.RO), ["-u", "077", "-R"])

    def test_sftp_credentials(self):
        with mock.patch.object(suc.pwd, "getpwnam") as m:
            m.return_value = mock.Mock(pw_uid=1002, pw_gid=2000)
            self.assertEqual(suc.sftp_credentials(), (1002, 2000))
            m.assert_called_once_with("svc-sys-usb-sftp")

    def test_sftp_credentials_missing_account(self):
        with mock.patch.object(suc.pwd, "getpwnam", side_effect=KeyError):
            with self.assertRaises(KeyError):
                suc.sftp_credentials()

    def test_bwrap_args_rw(self):
        self.assertEqual(
            suc.bwrap_args(MountMode.RW, 1002, 2000, make_context()),
            [
                "bwrap",
                "--tmpfs",
                "/",
                "--dir",
                "/media/usb",
                "--bind",
                "/media/usb",
                "/media/usb",
                "--dir",
                "/etc",
                "--ro-bind",
                "/var/run/safecor/direct-mount/sftp-sandbox-passwd",
                "/etc/passwd",
                "--dir",
                "/bin",
                "--ro-bind",
                "/bin/setpriv",
                "/bin/setpriv",
                "--dir",
                "/lib",
                "--ro-bind",
                "/lib/ld-musl-x86_64.so.1",
                "/lib/ld-musl-x86_64.so.1",
                "--dir",
                "/usr",
                "--dir",
                "/usr/lib",
                "--ro-bind",
                "/usr/lib/libeconf.so.0",
                "/usr/lib/libeconf.so.0",
                "--ro-bind",
                "/usr/lib/libcap-ng.so.0",
                "/usr/lib/libcap-ng.so.0",
                "--dir",
                "/usr/lib/ssh",
                "--ro-bind",
                "/usr/lib/ssh/sftp-server",
                "/usr/lib/ssh/sftp-server",
                "--cap-drop",
                "ALL",
                "--cap-add",
                "CAP_SETUID",
                "--cap-add",
                "CAP_SETGID",
                "--cap-add",
                "CAP_SETPCAP",
                "--dev",
                "/dev",
                "--unshare-pid",
                "--unshare-ipc",
                "--unshare-uts",
                "--unshare-net",
                "--die-with-parent",
                "--chdir",
                "/media/usb",
                "--",
                "/bin/setpriv",
                "--reuid",
                "1002",
                "--regid",
                "2000",
                "--clear-groups",
                "--no-new-privs",
                "/usr/lib/ssh/sftp-server",
                "-u",
                "077",
            ],
        )

    def test_bwrap_args_ro(self):
        # The only deltas between the RO and the RW command lines are the
        # read-only bind of /media/usb and the -R sftp-server argument.
        rw = suc.bwrap_args(MountMode.RW, 1002, 2000, make_context())
        ro = suc.bwrap_args(MountMode.RO, 1002, 2000, make_context())
        self.assertEqual(ro[:5], rw[:5])
        self.assertEqual(ro[5:8], ["--ro-bind", "/media/usb", "/media/usb"])
        self.assertEqual(ro[8:-1], rw[8:])
        self.assertEqual(ro[-1], "-R")

    def test_parse_ldd_output(self):
        # A setpriv 2.42 (util-linux) ldd output on a musl system.
        output = (
            "\tld-linux-x86-64.so.2 => /lib/ld-musl-x86_64.so.1 (0x7f0000000000)\n"
            "\tlibcap-ng.so.0 => /usr/lib/libcap-ng.so.0 (0x7f0000001000)\n"
            "\tlibeconf.so.0 => /usr/lib/libeconf.so.0 (0x7f0000002000)\n"
            "\tlibc.musl-x86_64.so.1 => /lib/ld-musl-x86_64.so.1 "
            "(0x7f0000003000)\n"
            "\tlibmissing.so.0 => not found\n"
        )
        self.assertEqual(
            suc.parse_ldd_output(output),
            ["/usr/lib/libcap-ng.so.0", "/usr/lib/libeconf.so.0"],
        )

    def test_parse_ldd_output_skips_musl_and_dedups(self):
        output = (
            "\tlibfoo.so.0 => /usr/lib/libfoo.so.0 (0x1)\n"
            "\tlibfoo.so.0 => /usr/lib/libfoo.so.0 (0x1)\n"
            "\tlibc.so.0 => /lib/libc.so.0 (0x2)\n"
            "statically linked\n"
        )
        self.assertEqual(
            suc.parse_ldd_output(output),
            ["/usr/lib/libfoo.so.0", "/lib/libc.so.0"],
        )

    def test_parse_ldd_output_empty(self):
        self.assertEqual(suc.parse_ldd_output(""), [])
        self.assertEqual(suc.parse_ldd_output("statically linked\n"), [])

    def test_setpriv_library_paths(self):
        ldd_output = (
            "\tld-linux-x86-64.so.2 => /lib/ld-musl-x86_64.so.1 (0x1)\n"
            "\tlibcap-ng.so.0 => /usr/lib/libcap-ng.so.0 (0x2)\n"
        )
        with mock.patch.object(
            suc.subprocess, "run", return_value=mock.Mock(stdout=ldd_output)
        ) as m:
            self.assertEqual(
                suc.setpriv_library_paths("/bin/setpriv"),
                ["/usr/lib/libcap-ng.so.0"],
            )
            m.assert_called_once()
            self.assertEqual(m.call_args.args[0], ["ldd", "/bin/setpriv"])

    def test_bind_dirs(self):
        self.assertEqual(
            suc.bind_dirs(
                ["/etc/passwd", "/usr/lib/ssh/sftp-server", "/usr/lib/libfoo.so.0"]
            ),
            ["/etc", "/usr", "/usr/lib", "/usr/lib/ssh"],
        )

    def test_bind_dirs_shallow_and_empty(self):
        self.assertEqual(suc.bind_dirs(["/setpriv"]), [])
        self.assertEqual(suc.bind_dirs([]), [])

    def test_write_sandbox_passwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "safecor" / "passwd")
            result = suc.write_sandbox_passwd(1002, 2000, path)
            self.assertEqual(result, path)
            self.assertEqual(
                Path(path).read_text(),
                "svc-sys-usb-sftp:x:1002:2000::/:/sbin/nologin\n",
            )
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)


class TestDirectMountComponentState(unittest.TestCase):
    """The safecor_direct_mount component published by the controller."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)

    def test_initial_states(self):
        self.assertEqual(
            self.controller._SysUsbController__controller_state,
            ComponentState.READY,
        )
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])

    def _published_states(self) -> dict:
        self.assertEqual(self.mqtt_client.publish.call_count, 1)
        topic, payload = self.mqtt_client.publish.call_args.args
        self.assertEqual(topic, f"{Topics.DISCOVER_COMPONENTS}/response")
        return {comp["id"]: comp["state"] for comp in payload["components"]}

    def test_publish_component_states_carries_direct_mount_state(self):
        self.controller._SysUsbController__publish_component_states()
        states = self._published_states()
        self.assertEqual(states[Constants.SAFECOR_DISK_CONTROLLER], "ready")
        self.assertEqual(states[Constants.SAFECOR_INPUT_CONTROLLER], "ready")
        self.assertEqual(states[Constants.SAFECOR_DIRECT_MOUNT], "starting")

    def test_handle_discover_components_reports_current_state(self):
        self.controller._SysUsbController__handle_discover_components()
        self.assertEqual(
            self._published_states()[Constants.SAFECOR_DIRECT_MOUNT], "starting"
        )

    def test_set_direct_mount_state_publishes(self):
        self.controller._SysUsbController__set_direct_mount_state(ComponentState.READY)
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.assertEqual(
            self._published_states()[Constants.SAFECOR_DIRECT_MOUNT], "ready"
        )


class TestMyConfigOneShot(unittest.TestCase):
    """The one-shot my_config query of the channel thread."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)

    def test_on_mqtt_message_routes_my_config_response(self):
        payload = {
            "domains": [
                {"name": "sys-usb", "direct_mount": False},
                {"name": "app1", "direct_mount": {"mode": "ro"}},
            ]
        }
        self.controller._SysUsbController__on_mqtt_message(
            f"{Topics.MY_CONFIG}/response", payload
        )
        self.assertEqual(self.controller._SysUsbController__my_config_result, payload)
        self.assertTrue(self.controller._SysUsbController__my_config_event.is_set())

    def test_on_mqtt_message_ignores_filtered_response(self):
        # A response filtered for another domain never lists sys-usb
        # itself: it is not the one we asked for.
        payload = {"domains": [{"name": "app1", "direct_mount": {"mode": "ro"}}]}
        self.controller._SysUsbController__on_mqtt_message(
            f"{Topics.MY_CONFIG}/response", payload
        )
        self.assertIsNone(self.controller._SysUsbController__my_config_result)
        self.assertFalse(self.controller._SysUsbController__my_config_event.is_set())

    def test_accept_my_config_response(self):
        full = {
            "domains": [
                {"name": "sys-usb", "direct_mount": False},
                {"name": "app1", "direct_mount": {"mode": "rw"}},
            ]
        }
        filtered = {"domains": [{"name": "app1", "direct_mount": {"mode": "rw"}}]}
        self.assertTrue(
            self.controller._SysUsbController__accept_my_config_response(full)
        )
        self.assertFalse(
            self.controller._SysUsbController__accept_my_config_response(filtered)
        )

    def test_query_direct_mount_domains(self):
        # The query clears its state, publishes the request and waits for
        # the routed response: the mock publish simulates that response
        # (as __on_mqtt_message does in production).
        def publish(topic, payload):
            self.assertEqual(topic, f"{Topics.MY_CONFIG}/request")
            self.assertEqual(payload, {})
            self.controller._SysUsbController__my_config_result = {
                "domains": [{"name": "app1", "direct_mount": {"mode": "ro"}}]
            }
            self.controller._SysUsbController__my_config_event.set()

        self.mqtt_client.publish = mock.Mock(side_effect=publish)
        self.assertEqual(
            self.controller._SysUsbController__query_direct_mount_domains(),
            [("app1", MountMode.RO)],
        )
        self.mqtt_client.publish.assert_called_once()

    def test_query_direct_mount_domains_timeout(self):
        with mock.patch.object(
            self.controller._SysUsbController__my_config_event,
            "wait",
            return_value=False,
        ):
            self.assertIsNone(
                self.controller._SysUsbController__query_direct_mount_domains()
            )


class TestStartDirectMountChannels(unittest.TestCase):
    """The channel start pass (dedicated thread)."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)
        self.controller._SysUsbController__run_channels_helper = mock.MagicMock(
            return_value=True
        )

    def test_query_failed_stays_starting(self):
        with mock.patch.object(
            SysUsbController,
            "_SysUsbController__query_direct_mount_domains",
            return_value=None,
        ):
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        self.controller._SysUsbController__run_channels_helper.assert_not_called()

    def test_zero_domains_ready(self):
        with mock.patch.object(
            SysUsbController,
            "_SysUsbController__query_direct_mount_domains",
            return_value=[],
        ):
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.controller._SysUsbController__run_channels_helper.assert_not_called()

    def test_missing_domid_skipped_still_ready(self):
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("safecor._sys_usb_controller.System") as system,
        ):
            system.return_value.get_domain_domid.return_value = None
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.controller._SysUsbController__run_channels_helper.assert_not_called()

    def test_normal_case_starts_channels(self):
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW), ("app2", MountMode.RO)],
            ),
            mock.patch("safecor._sys_usb_controller.System") as system,
        ):
            system.return_value.get_domain_domid.side_effect = [5, 6]
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.assertEqual(
            self.controller._SysUsbController__sftp_channels, ["app1", "app2"]
        )
        self.assertEqual(
            self.controller._SysUsbController__run_channels_helper.call_args_list,
            [
                mock.call(
                    {
                        "action": "start",
                        "name": "app1",
                        "domid": 5,
                        "mode": "rw",
                    }
                ),
                mock.call(
                    {
                        "action": "start",
                        "name": "app2",
                        "domid": 6,
                        "mode": "ro",
                    }
                ),
            ],
        )

    def test_helper_failure_channel_not_tracked(self):
        self.controller._SysUsbController__run_channels_helper.return_value = False
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("safecor._sys_usb_controller.System") as system,
        ):
            system.return_value.get_domain_domid.return_value = 5
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])


class TestChannelsHelper(unittest.TestCase):
    """The doas invocation of the root channels helper."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)

    def test_run_channels_helper_success(self):
        with mock.patch(
            "safecor._sys_usb_controller.subprocess.run",
            return_value=mock.Mock(returncode=0, stderr=""),
        ) as run:
            ok = self.controller._SysUsbController__run_channels_helper(
                {"action": "start", "name": "app1", "domid": 5, "mode": "rw"}
            )
        self.assertTrue(ok)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "/usr/bin/doas")
        self.assertEqual(cmd[1], suc.DM_CHANNELS_HELPER)
        self.assertEqual(
            json.loads(cmd[2]),
            {"action": "start", "name": "app1", "domid": 5, "mode": "rw"},
        )

    def test_run_channels_helper_failure(self):
        with mock.patch(
            "safecor._sys_usb_controller.subprocess.run",
            return_value=mock.Mock(returncode=1, stderr="boom"),
        ):
            ok = self.controller._SysUsbController__run_channels_helper(
                {"action": "stop", "name": "app1"}
            )
        self.assertFalse(ok)

    def test_run_channels_helper_oserror(self):
        with mock.patch(
            "safecor._sys_usb_controller.subprocess.run",
            side_effect=OSError("doas not found"),
        ):
            ok = self.controller._SysUsbController__run_channels_helper(
                {"action": "stop", "name": "app1"}
            )
        self.assertFalse(ok)

    def test_stop_direct_mount_channels(self):
        self.controller._SysUsbController__sftp_channels = ["app1", "app2"]
        with mock.patch.object(
            SysUsbController,
            "_SysUsbController__run_channels_helper",
            return_value=True,
        ) as helper:
            self.controller._SysUsbController__stop_direct_mount_channels()
        self.assertEqual(
            helper.call_args_list,
            [
                mock.call({"action": "stop", "name": "app1"}),
                mock.call({"action": "stop", "name": "app2"}),
            ],
        )
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])


class TestShutdown(unittest.TestCase):
    """The OFF state on restart and stop (best-effort channel stop)."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)

    def test_handle_restart_sys_usb(self):
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__stop_direct_mount_channels",
            ) as stop_channels,
            mock.patch(
                "safecor._sys_usb_controller.subprocess.run",
                return_value=mock.Mock(returncode=0),
            ) as run,
        ):
            self.controller._SysUsbController__handle_restart(
                {"domain_name": "sys-usb"}
            )
        # All the components are published OFF, before the reboot
        states = {
            comp["id"]: comp["state"]
            for comp in self.mqtt_client.publish.call_args.args[1]["components"]
        }
        self.assertEqual(states[Constants.SAFECOR_DISK_CONTROLLER], "off")
        self.assertEqual(states[Constants.SAFECOR_INPUT_CONTROLLER], "off")
        self.assertEqual(states[Constants.SAFECOR_DIRECT_MOUNT], "off")
        self.assertEqual(
            self.controller._SysUsbController__controller_state,
            ComponentState.OFF,
        )
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.OFF,
        )
        stop_channels.assert_called_once()
        self.assertTrue(
            any(
                call.args[0] == ["/usr/bin/doas", "/sbin/reboot"]
                for call in run.call_args_list
            )
        )

    def test_handle_restart_other_domain_noop(self):
        with mock.patch("safecor._sys_usb_controller.subprocess.run") as run:
            self.controller._SysUsbController__handle_restart({"domain_name": "app1"})
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        run.assert_not_called()
        self.mqtt_client.publish.assert_not_called()

    def test_stop(self):
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__stop_direct_mount_channels",
            ) as stop_channels,
            mock.patch("safecor._sys_usb_controller.InputsDaemon"),
        ):
            self.controller.stop()
        self.assertFalse(self.controller._SysUsbController__can_run)
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.OFF,
        )
        stop_channels.assert_called_once()


if __name__ == "__main__":
    unittest.main()
