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
import shlex
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
        bwrap="/usr/bin/bwrap",
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
        self.assertEqual(suc.SANDBOX_WRAPPER_DIR, "/usr/lib/safecor/tmp")
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
                "/usr/bin/bwrap",
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

    def test_sandbox_wrapper_path(self):
        self.assertEqual(
            suc.sandbox_wrapper_path("app1"),
            "/usr/lib/safecor/tmp/sandbox-app1",
        )

    def test_write_sandbox_wrapper(self):
        with mock.patch.object(
            suc, "SANDBOX_WRAPPER_DIR", tempfile.mkdtemp()
        ) as tmpdir:
            path = suc.write_sandbox_wrapper(
                "app1", ["/usr/bin/bwrap", "--ro-bind", "/tmp/my bwrap", "/"]
            )
            self.assertEqual(path, f"{tmpdir}/sandbox-app1")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o755)
            content = Path(path).read_text()
            self.assertTrue(content.startswith("#!/bin/sh\nexec "))
            # Verify the argument with a space is shlex-quoted
            self.assertIn(shlex.quote("/tmp/my bwrap"), content)

    def test_stop_sftp_channel_removes_wrapper(self):
        with (
            mock.patch.object(suc, "SANDBOX_WRAPPER_DIR", tempfile.mkdtemp()) as tmpdir,
            mock.patch("safecor._sys_usb_controller.subprocess.run"),
        ):
            # Create a wrapper file
            wrapper_path = os.path.join(tmpdir, "sandbox-app1")
            Path(wrapper_path).touch()
            self.assertTrue(Path(wrapper_path).exists())
            suc.stop_sftp_channel("app1")
            self.assertFalse(Path(wrapper_path).exists())

    def test_stop_sftp_channel_no_wrapper_ok(self):
        with (
            mock.patch.object(suc, "SANDBOX_WRAPPER_DIR", tempfile.mkdtemp()),
            mock.patch("safecor._sys_usb_controller.subprocess.run"),
        ):
            # No wrapper to remove — should not raise
            suc.stop_sftp_channel("app1")

    def test_start_sftp_channel_uses_short_address(self):
        with (
            mock.patch.object(suc, "SANDBOX_WRAPPER_DIR", tempfile.mkdtemp()) as tmpdir,
            mock.patch("safecor._sys_usb_controller.subprocess.run") as run_mock,
        ):
            suc.start_sftp_channel(
                "app1",
                domid=5,
                mode=MountMode.RW,
                uid=1002,
                gid=2000,
                ctx=make_context(),
            )
            # Check that the socat start command uses the short wrapper address
            # start_sftp_channel calls subprocess.run twice: once for socat,
            # once for vchan-socket-proxy. We filter for the socat call.
            socat_calls = [
                c
                for c in run_mock.call_args_list
                if any("/usr/bin/socat" in str(a) for a in c.args)
            ]
            self.assertEqual(len(socat_calls), 1)
            argv = socat_calls[0].args[0]
            # The EXEC address should be short (wrapper path)
            exec_addr = [a for a in argv if a.startswith("EXEC:")]
            self.assertEqual(len(exec_addr), 1)
            self.assertIn(f'EXEC:"{tmpdir}/sandbox-app1"', exec_addr)
            # The full bwrap command should NOT be in argv
            full_cmd = " ".join(argv)
            self.assertNotIn("/usr/bin/bwrap --tmpfs", full_cmd)
            # The wrapper file should exist and contain the full command
            wrapper_path = os.path.join(tmpdir, "sandbox-app1")
            self.assertTrue(Path(wrapper_path).exists())
            content = Path(wrapper_path).read_text()
            self.assertIn("/usr/bin/bwrap --tmpfs", content)


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

    def test_accept_my_config_response_with_direct_mount_domains(self):
        # Full topology WITH direct_mount_domains → accepted.
        full = {
            "domains": [
                {"name": "sys-usb"},
                {"name": "saphir-av-clamav"},
                {"name": "saphir-av-eset"},
            ],
            "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"],
        }
        self.assertTrue(
            self.controller._SysUsbController__accept_my_config_response(full)
        )

    def test_accept_my_config_response_filtered_for_sysusb_rejected(self):
        # The bug: response filtered for sys-usb (no other domains in
        # domains, but direct_mount_domains still global) → rejected.
        filtered = {
            "domains": [{"name": "sys-usb"}],
            "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"],
        }
        self.assertFalse(
            self.controller._SysUsbController__accept_my_config_response(filtered)
        )

    def test_accept_my_config_response_filtered_for_other_domain_rejected(self):
        # Filtered for a non-sys-usb direct-mount domain → rejected
        # (no sys-usb in domains).
        filtered = {
            "domains": [{"name": "saphir-av-clamav"}],
            "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"],
        }
        self.assertFalse(
            self.controller._SysUsbController__accept_my_config_response(filtered)
        )

    def test_accept_my_config_response_no_direct_mount_domains_accepted(self):
        # Degenerate case: no direct-mount domains in topology, empty
        # list → accepted (parses to empty pair list — correct).
        empty = {
            "domains": [{"name": "sys-usb"}],
            "direct_mount_domains": [],
        }
        self.assertTrue(
            self.controller._SysUsbController__accept_my_config_response(empty)
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
        """Missing domid (timeout) → channel skipped, component stays STARTING."""
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
            ComponentState.STARTING,
        )
        self.controller._SysUsbController__run_channels_helper.assert_not_called()

    def test_normal_case_starts_channels(self):
        """All channels start and pass liveness → READY."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW), ("app2", MountMode.RO)],
            ),
            mock.patch("safecor._sys_usb_controller.System") as system,
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
            mock.patch("time.sleep"),
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
        """Helper failure → channel skipped, component stays STARTING."""
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
            ComponentState.STARTING,
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


class TestStartChannelsAllOrNothingReady(unittest.TestCase):
    """F1: READY only when ALL channels are started and verified alive."""

    def setUp(self):
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)
        self.controller._SysUsbController__run_channels_helper = mock.MagicMock(
            return_value=True
        )
        # Patch the wait_for_domid so domid resolution is instant.
        self.controller._SysUsbController__wait_for_domid = mock.Mock(return_value=5)

    def test_all_channels_fail_helper(self):
        """All helper calls fail → component stays STARTING."""
        self.controller._SysUsbController__run_channels_helper.return_value = False
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW), ("app2", MountMode.RO)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
        ):
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        # No channels tracked (all failed)
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])

    def test_partial_failure(self):
        """1 of 2 domains fails → component stays STARTING."""
        self.controller._SysUsbController__run_channels_helper.side_effect = [
            False,  # app1 fails
            True,  # app2 succeeds
        ]
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW), ("app2", MountMode.RO)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists") as mock_exists,
            mock.patch("pathlib.Path.read_text") as mock_read,
        ):
            # Make liveness verification pass for app2 (the one that succeeded)
            mock_exists.return_value = True
            mock_read.return_value = "9999\n"
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        # Only app2 should be tracked
        self.assertEqual(self.controller._SysUsbController__sftp_channels, ["app2"])

    def test_all_channels_verified_alive(self):
        """All channels start and pass liveness → READY."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW), ("app2", MountMode.RO)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists") as mock_exists,
            mock.patch("pathlib.Path.read_text") as mock_read,
            mock.patch("time.sleep"),
        ):
            mock_exists.return_value = True
            mock_read.return_value = "9999\n"
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.assertEqual(
            self.controller._SysUsbController__sftp_channels,
            ["app1", "app2"],
        )

    def test_domid_returns_none_then_value(self):
        """Domid appears after a delay: the bounded wait finds it.

        Simulates __wait_for_domid eventually resolving a domid (3) for
        "app1", exercising the all-or-nothing READY logic.
        """
        # Reset the setUp mock's call count so assertion works.
        self.controller._SysUsbController__run_channels_helper.reset_mock()
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__wait_for_domid",
                return_value=3,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
            mock.patch("time.sleep"),
        ):
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )
        self.controller._SysUsbController__run_channels_helper.assert_called_once_with(
            {"action": "start", "name": "app1", "domid": 3, "mode": "rw"}
        )

    def test_empty_pairs_ready(self):
        """Empty pairs → READY (backward compatible)."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
        ):
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )

    def test_liveness_verification_passes(self):
        """Pidfiles exist, procs alive, socket exists → verification passes."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists") as mock_exists,
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
            mock.patch("time.sleep"),
        ):
            mock_exists.return_value = True
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.READY,
        )

    def test_liveness_verification_fails_missing_socket(self):
        """Socket doesn't exist → liveness fails → channel not tracked."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists") as mock_exists,
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
            mock.patch("time.sleep"),
        ):
            # pidfile procs exist, but vchan socket doesn't
            mock_exists.side_effect = lambda p: not p.endswith(".sock")
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])

    def test_liveness_verification_fails_missing_pidfile(self):
        """Pidfile doesn't exist → liveness fails."""
        with (
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch.object(
                SysUsbController,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch("os.path.exists") as mock_exists,
            mock.patch("pathlib.Path.read_text", side_effect=FileNotFoundError),
            mock.patch("time.sleep"),
        ):
            mock_exists.return_value = True
            self.controller._SysUsbController__start_direct_mount_channels()
        self.assertEqual(
            self.controller._SysUsbController__direct_mount_state,
            ComponentState.STARTING,
        )
        self.assertEqual(self.controller._SysUsbController__sftp_channels, [])


# ---------------------------------------------------------------------------
# Supervisor thread tests (ADR 0006 — self-heal after domain self-restart)
# ---------------------------------------------------------------------------


class TestChannelSupervisor(unittest.TestCase):
    """Unit tests for the SFTP channel supervisor thread."""

    def setUp(self):
        self.mqtt = mock.MagicMock()
        self.mqtt_client = mock.MagicMock()
        self.controller = SysUsbController(self.mqtt_client)
        self.controller._SysUsbController__can_run = True

    # --- __update_cached_domids ----------------------------------------

    def test_update_cached_domids_reads_from_system(self):
        """__update_cached_domids calls System().get_domain_domid()."""
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("sys-usb", MountMode.RW)],
            ),
            mock.patch.object(suc.System, "get_domain_domid") as get_domid,
        ):
            get_domid.return_value = 42
            self.controller._SysUsbController__update_cached_domids()
        get_domid.assert_called_once_with("sys-usb")
        self.assertEqual(
            self.controller._SysUsbController__channels_domids,
            {"sys-usb": 42},
        )

    def test_update_cached_domids_ignores_none(self):
        """None domid → last known value kept, not deleted."""
        self.controller._SysUsbController__channels_domids = {"sys-usb": 10}
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("sys-usb", MountMode.RW)],
            ),
            mock.patch.object(suc.System, "get_domain_domid") as get_domid,
        ):
            get_domid.return_value = None
            self.controller._SysUsbController__update_cached_domids()
        # Value unchanged.
        self.assertEqual(
            self.controller._SysUsbController__channels_domids,
            {"sys-usb": 10},
        )

    def test_update_cached_domids_updates_on_difference(self):
        """Different domid → updated in cache."""
        self.controller._SysUsbController__channels_domids = {"sys-usb": 10}
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("sys-usb", MountMode.RW)],
            ),
            mock.patch.object(suc.System, "get_domain_domid") as get_domid,
        ):
            get_domid.return_value = 20
            self.controller._SysUsbController__update_cached_domids()
        self.assertEqual(
            self.controller._SysUsbController__channels_domids,
            {"sys-usb": 20},
        )

    def test_update_cached_domids_skips_unchanged(self):
        """Same domid → no write-back."""
        self.controller._SysUsbController__channels_domids = {"sys-usb": 10}
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("sys-usb", MountMode.RW)],
            ),
            mock.patch.object(suc.System, "get_domain_domid") as get_domid,
        ):
            get_domid.return_value = 10
            self.controller._SysUsbController__update_cached_domids()
        self.assertEqual(
            self.controller._SysUsbController__channels_domids,
            {"sys-usb": 10},
        )

    def test_update_cached_domids_no_domains(self):
        """No direct_mount domains → nothing updated."""
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[],
            ),
            mock.patch.object(suc.System, "get_domain_domid"),
        ):
            self.controller._SysUsbController__update_cached_domids()
        self.assertEqual(self.controller._SysUsbController__channels_domids, {})

    # --- __is_channel_alive -------------------------------------------

    def test_is_channel_alive_all_present(self):
        """Both pidfiles + socket present → True."""
        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
        ):
            self.assertTrue(
                self.controller._SysUsbController__is_channel_alive("app1", 10)
            )

    def test_is_channel_alive_missing_socket(self):
        """Socket missing → False."""
        with (
            mock.patch("os.path.exists", side_effect=lambda p: not p.endswith(".sock")),
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
        ):
            self.assertFalse(
                self.controller._SysUsbController__is_channel_alive("app1", 10)
            )

    def test_is_channel_alive_missing_pidfile(self):
        """Pidfile missing → False."""
        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_text", side_effect=FileNotFoundError),
        ):
            self.assertFalse(
                self.controller._SysUsbController__is_channel_alive("app1", 10)
            )

    def test_is_channel_alive_dead_process(self):
        """Pidfile exists but /proc/<pid> missing → False."""
        with (
            mock.patch(
                "os.path.exists",
                side_effect=lambda p: p != "/proc/9999" and not p.endswith(".sock"),
            ),
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
        ):
            self.assertFalse(
                self.controller._SysUsbController__is_channel_alive("app1", 10)
            )

    # --- __reconcile_channels -----------------------------------------

    def test_reconcile_starts_missing_channel(self):
        """Domain in cache but not in sftp_channels → channel started."""
        self.controller._SysUsbController__channels_domids = {"app1": 10}
        self.controller._SysUsbController__sftp_channels = []
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            self.assertIn("app1", self.controller._SysUsbController__sftp_channels)
            # Helper was called for the missing channel.
            call_list = (
                self.controller._SysUsbController__run_channels_helper.call_args_list
            )
            self.assertEqual(len(call_list), 1)
            self.assertEqual(call_list[0][0][0]["action"], "start")

    def test_reconcile_restarts_dead_channel(self):
        """Dead channel → restarted with cached domid, no duplicate entry."""
        self.controller._SysUsbController__channels_domids = {"app1": 10}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=False,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            # Only one entry (no duplicate from append).
            self.assertEqual(self.controller._SysUsbController__sftp_channels, ["app1"])
            # Verify the call spec includes mode.
            call_spec = (
                self.controller._SysUsbController__run_channels_helper.call_args_list[
                    0
                ][0][0]
            )
            self.assertEqual(call_spec["action"], "start")
            self.assertEqual(call_spec["domid"], 10)
            self.assertEqual(call_spec["mode"], "rw")

    def test_reconcile_two_ticks_healthy_no_extra_calls(self):
        """Two consecutive ticks with healthy channel → no duplicate entries."""
        self.controller._SysUsbController__channels_domids = {"app1": 10}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__get_channel_domid",
                return_value=10,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            # Tick 1: healthy → no action.
            self.controller._SysUsbController__reconcile_channels()
            count_after_1 = (
                self.controller._SysUsbController__run_channels_helper.call_count
            )
            # Tick 2: healthy → no extra calls.
            self.controller._SysUsbController__reconcile_channels()
            count_after_2 = (
                self.controller._SysUsbController__run_channels_helper.call_count
            )
            self.assertEqual(count_after_1, 0)
            self.assertEqual(count_after_2, 0)
            self.assertEqual(self.controller._SysUsbController__sftp_channels, ["app1"])

    def test_reconcile_supervisor_order_update_before_reconcile(self):
        """__update_cached_domids runs before __reconcile_channels."""
        order = []
        original_reconcile = self.controller._SysUsbController__reconcile_channels

        def patched_update():
            order.append("update")
            # Stop the loop after first iteration by setting __can_run to False
            self.controller._SysUsbController__can_run = False

        def patched_reconcile():
            order.append("reconcile")
            original_reconcile()

        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__update_cached_domids",
                side_effect=patched_update,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__reconcile_channels",
                side_effect=patched_reconcile,
            ),
            mock.patch("time.sleep"),
        ):
            self.controller._SysUsbController__channel_supervisor()
            self.assertEqual(order, ["update", "reconcile"])

    # --- __get_channel_domid --------------------------------------------

    def test_get_channel_domid_success(self):
        """Parses cmdline → returns the domid after 'server'."""
        cmdline = b"vchan-socket-proxy\x00-m\x00server\x0042\x00/local/foo\x00/tmp/sock"
        with (
            mock.patch("pathlib.Path.read_text", return_value="100\n"),
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_bytes", return_value=cmdline),
        ):
            result = self.controller._SysUsbController__get_channel_domid("app1")
            self.assertEqual(result, 42)

    def test_get_channel_domid_process_gone(self):
        """/proc/<pid> missing → None."""
        with (
            mock.patch("pathlib.Path.read_text", return_value="9999\n"),
            mock.patch("os.path.exists", return_value=False),
        ):
            result = self.controller._SysUsbController__get_channel_domid("app1")
            self.assertIsNone(result)

    def test_get_channel_domid_pidfile_bad(self):
        """Corrupt pidfile → None."""
        with mock.patch("pathlib.Path.read_text", return_value="not-a-pid\n"):
            result = self.controller._SysUsbController__get_channel_domid("app1")
            self.assertIsNone(result)

    def test_get_channel_domid_no_server_token(self):
        """No 'server' token in cmdline → None."""
        cmdline = b"vchan-socket-proxy\x00-m\x00client\x0042\x00/local/foo\x00/tmp/sock"
        with (
            mock.patch("pathlib.Path.read_text", return_value="100\n"),
            mock.patch("os.path.exists", return_value=True),
            mock.patch("pathlib.Path.read_bytes", return_value=cmdline),
        ):
            result = self.controller._SysUsbController__get_channel_domid("app1")
            self.assertIsNone(result)

    # --- __reconcile_channels: re-pin ----------------------------------

    def test_reconcile_repin_on_domid_change(self):
        """Alive channel with stale cmdline domid → re-pin with new domid."""
        self.controller._SysUsbController__channels_domids = {"app1": 42}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__get_channel_domid",
                return_value=10,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            # Exactly one call (re-pin), no append to sftp_channels
            self.assertEqual(
                self.controller._SysUsbController__run_channels_helper.call_count, 1
            )
            self.assertEqual(self.controller._SysUsbController__sftp_channels, ["app1"])
            call_spec = (
                self.controller._SysUsbController__run_channels_helper.call_args_list[
                    0
                ][0][0]
            )
            self.assertEqual(call_spec["domid"], 42)
            self.assertEqual(call_spec["mode"], "rw")

    def test_reconcile_repin_no_action_when_matching(self):
        """Alive channel with matching cmdline domid → no helper call."""
        self.controller._SysUsbController__channels_domids = {"app1": 42}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__get_channel_domid",
                return_value=42,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            self.assertEqual(
                self.controller._SysUsbController__run_channels_helper.call_count, 0
            )

    def test_reconcile_repin_unparseable_cmdline_restart(self):
        """Unparseable cmdline → treated as dead → restart."""
        self.controller._SysUsbController__channels_domids = {"app1": 42}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__get_channel_domid",
                return_value=None,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            self.assertEqual(
                self.controller._SysUsbController__run_channels_helper.call_count, 1
            )

    def test_reconcile_dead_channel_includes_mode(self):
        """Dead-channel restart includes the mode from topology."""
        self.controller._SysUsbController__channels_domids = {"app1": 10}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=False,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RO)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            call_spec = (
                self.controller._SysUsbController__run_channels_helper.call_args_list[
                    0
                ][0][0]
            )
            self.assertEqual(call_spec["action"], "start")
            self.assertEqual(call_spec["domid"], 10)
            self.assertEqual(call_spec["mode"], "ro")

    def test_reconcile_default_mode_rw(self):
        """When mode is absent from topology, defaults to 'rw'."""
        self.controller._SysUsbController__channels_domids = {"app1": 10}
        self.controller._SysUsbController__sftp_channels = ["app1"]
        with (
            mock.patch.object(
                self.controller,
                "_SysUsbController__is_channel_alive",
                return_value=False,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__run_channels_helper",
                return_value=True,
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__log_channel_event",
            ),
            mock.patch.object(
                self.controller,
                "_SysUsbController__query_direct_mount_domains",
                return_value=[("app1", MountMode.RW)],
            ),
            mock.patch("os.path.exists", return_value=True),
        ):
            self.controller._SysUsbController__reconcile_channels()
            call_spec = (
                self.controller._SysUsbController__run_channels_helper.call_args_list[
                    0
                ][0][0]
            )
            self.assertEqual(call_spec["mode"], "rw")


if __name__ == "__main__":
    unittest.main()
