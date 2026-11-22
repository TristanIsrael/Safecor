"""Unit tests for the event-driven DirectMountManager.

The manager reacts to the bus events instead of polling (NFR-3): the
``safecor_direct_mount`` component state triggers the mount (READY) or the
unmount (OFF), and the one-shot my_config query determines the mount mode.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from safecor import (
    ComponentsHelper,
    ComponentState,
    Constants,
    DirectMountManager,
    MountMode,
    Topics,
)
from safecor import _direct_mount_manager as dmm

DOMAIN = "app1"


def components_payload(state: ComponentState) -> dict:
    """A discover_components response with the direct mount component."""
    return {
        "domains": [],
        "components": [
            {
                "id": Constants.SAFECOR_DIRECT_MOUNT,
                "desc": "Direct USB mount (SFTP channels)",
                "domain": "sys-usb",
                "state": state.value,
                "type": "core",
            }
        ],
    }


class DirectMountManagerBase(unittest.TestCase):
    def setUp(self):
        # ComponentsHelper keeps its list at class level: clear it so the
        # tests do not see each other's components.
        ComponentsHelper().clear()

        # The Api (a singleton with class-level callback lists) is mocked:
        # the manager under test never touches a real MQTT client.
        self._api_patcher = patch.object(dmm, "Api")
        self._api_patcher.start()
        self.manager = DirectMountManager()
        self.api = self.manager._DirectMountManager__api

    def tearDown(self):
        self._api_patcher.stop()

    def _state(self, state: ComponentState) -> None:
        self.manager._DirectMountManager__component_state = state


class TestDirectMountManagerBasics(DirectMountManagerBase):
    def test_get_mount_point(self):
        self.assertEqual(self.manager.get_mount_point(), Constants.USB_MOUNT_POINT)

    def test_is_mounted_initially_false(self):
        self.assertFalse(self.manager.is_mounted())

    def test_initial_states(self):
        self.assertIsNone(self.manager._DirectMountManager__mount_mode)
        self.assertEqual(
            self.manager._DirectMountManager__component_state,
            ComponentState.UNKNOWN,
        )
        self.assertFalse(self.manager._DirectMountManager__disabled)
        self.assertFalse(self.manager._DirectMountManager__running)


class TestParseMountMode(DirectMountManagerBase):
    def _parse(self, payload: dict):
        return self.manager._DirectMountManager__parse_mount_mode(payload)

    @patch("safecor._direct_mount_manager.System")
    def test_ro(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": DOMAIN, "direct_mount": {"mode": "ro"}}]}
        self.assertEqual(self._parse(payload), MountMode.RO)

    @patch("safecor._direct_mount_manager.System")
    def test_rw(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": DOMAIN, "direct_mount": {"mode": "rw"}}]}
        self.assertEqual(self._parse(payload), MountMode.RW)

    @patch("safecor._direct_mount_manager.System")
    def test_invalid_mode_defaults_to_rw(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": DOMAIN, "direct_mount": {"mode": "weird"}}]}
        self.assertEqual(self._parse(payload), MountMode.RW)

    @patch("safecor._direct_mount_manager.System")
    def test_dict_without_mode_defaults_to_rw(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        # A truthy dict without a "mode" key defaults to RW.
        payload = {"domains": [{"name": DOMAIN, "direct_mount": {"other": "x"}}]}
        self.assertEqual(self._parse(payload), MountMode.RW)

    @patch("safecor._direct_mount_manager.System")
    def test_empty_dict_is_disabled(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        # A falsy direct_mount (an empty dict) is "not enabled".
        payload = {"domains": [{"name": DOMAIN, "direct_mount": {}}]}
        self.assertIs(self._parse(payload), False)

    @patch("safecor._direct_mount_manager.System")
    def test_non_dict_truthy_defaults_to_rw(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": DOMAIN, "direct_mount": True}]}
        self.assertEqual(self._parse(payload), MountMode.RW)

    @patch("safecor._direct_mount_manager.System")
    def test_falsy_is_disabled(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": DOMAIN, "direct_mount": False}]}
        self.assertIs(self._parse(payload), False)

    @patch("safecor._direct_mount_manager.System")
    def test_domain_absent_is_none(self, mock_system):
        # A response for another domain: no definitive answer.
        mock_system.domain_name.return_value = DOMAIN
        payload = {"domains": [{"name": "other", "direct_mount": {"mode": "ro"}}]}
        self.assertIsNone(self._parse(payload))

    @patch("safecor._direct_mount_manager.System")
    def test_empty_payload_is_none(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        self.assertIsNone(self._parse({}))


class TestOnMyConfigResponse(DirectMountManagerBase):
    @patch("safecor._direct_mount_manager.System")
    def test_own_domain_sets_mode(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        self.manager._DirectMountManager__on_my_config_response(
            {"domains": [{"name": DOMAIN, "direct_mount": {"mode": "ro"}}]}
        )
        self.assertEqual(self.manager._DirectMountManager__mount_mode, MountMode.RO)
        self.assertFalse(self.manager._DirectMountManager__disabled)
        self.assertTrue(self.manager._DirectMountManager__my_config_event.is_set())
        self.assertTrue(self.manager._DirectMountManager__work_event.is_set())

    @patch("safecor._direct_mount_manager.System")
    def test_own_domain_falsy_disables(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        self.manager._DirectMountManager__on_my_config_response(
            {"domains": [{"name": DOMAIN, "direct_mount": False}]}
        )
        self.assertIsNone(self.manager._DirectMountManager__mount_mode)
        self.assertTrue(self.manager._DirectMountManager__disabled)
        self.assertTrue(self.manager._DirectMountManager__my_config_event.is_set())
        self.assertTrue(self.manager._DirectMountManager__work_event.is_set())

    @patch("safecor._direct_mount_manager.System")
    def test_other_domain_is_ignored(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        self.manager._DirectMountManager__on_my_config_response(
            {"domains": [{"name": "other", "direct_mount": {"mode": "ro"}}]}
        )
        self.assertIsNone(self.manager._DirectMountManager__mount_mode)
        self.assertFalse(self.manager._DirectMountManager__disabled)
        self.assertFalse(self.manager._DirectMountManager__my_config_event.is_set())
        self.assertFalse(self.manager._DirectMountManager__work_event.is_set())


class TestOnComponentsResponse(DirectMountManagerBase):
    def _fire(self, state: ComponentState, requery: MagicMock) -> MagicMock:
        """Fires a components response with the requery mock installed."""
        self.manager._DirectMountManager__query_my_config = requery
        self.manager._DirectMountManager__on_components_response(
            components_payload(state)
        )
        return requery

    def test_state_update(self):
        self._fire(ComponentState.READY, MagicMock())
        self.assertEqual(
            self.manager._DirectMountManager__component_state, ComponentState.READY
        )
        self.assertTrue(self.manager._DirectMountManager__work_event.is_set())

    def test_unknown_component_is_unknown(self):
        self.manager._DirectMountManager__on_components_response(
            {"components": [{"id": "other", "state": "ready"}]}
        )
        self.assertEqual(
            self.manager._DirectMountManager__component_state, ComponentState.UNKNOWN
        )

    def test_ready_triggers_one_shot_requery(self):
        self._fire(ComponentState.READY, MagicMock()).assert_called_once()

    def test_no_requery_when_mode_known(self):
        self.manager._DirectMountManager__mount_mode = MountMode.RW
        self._fire(ComponentState.READY, MagicMock()).assert_not_called()

    def test_no_requery_when_disabled(self):
        self.manager._DirectMountManager__disabled = True
        self._fire(ComponentState.READY, MagicMock()).assert_not_called()

    def test_requery_is_one_shot(self):
        # READY -> OFF -> READY: the requery must not be issued twice.
        requery = MagicMock()
        self._fire(ComponentState.READY, requery)
        self._fire(ComponentState.OFF, requery)
        self._fire(ComponentState.READY, requery)
        requery.assert_called_once()

    def test_same_state_twice_no_requery(self):
        requery = MagicMock()
        self._fire(ComponentState.READY, requery)
        self._fire(ComponentState.READY, requery)
        requery.assert_called_once()


class TestDoWork(DirectMountManagerBase):
    def _setup(self, state, mode=None, running=True, mounted=False):
        m = self.manager
        m._DirectMountManager__running = running
        m._DirectMountManager__component_state = state
        m._DirectMountManager__mount_mode = mode
        m._DirectMountManager__mounted = mounted
        return m

    def test_not_running_does_nothing(self):
        m = self._setup(ComponentState.READY, mode=MountMode.RW, running=False)
        m._DirectMountManager__generate_vchan_script = MagicMock()
        m._DirectMountManager__mount = MagicMock()
        m._DirectMountManager__do_work()
        m._DirectMountManager__generate_vchan_script.assert_not_called()
        m._DirectMountManager__mount.assert_not_called()

    def test_disabled_stops(self):
        m = self._setup(ComponentState.READY, mode=MountMode.RW)
        m._DirectMountManager__disabled = True
        stop = MagicMock()
        m.stop = stop
        m._DirectMountManager__do_work()
        stop.assert_called_once()

    def test_off_unmounts_when_mounted(self):
        m = self._setup(ComponentState.OFF, mode=MountMode.RW, mounted=True)
        unmount = MagicMock()
        m._DirectMountManager__unmount_mount = unmount
        m._DirectMountManager__do_work()
        unmount.assert_called_once()

    def test_off_without_mount_does_nothing(self):
        m = self._setup(ComponentState.OFF, mode=MountMode.RW)
        unmount = MagicMock()
        m._DirectMountManager__unmount_mount = unmount
        m._DirectMountManager__do_work()
        unmount.assert_not_called()

    def test_ready_with_mode_mounts(self):
        m = self._setup(ComponentState.READY, mode=MountMode.RW)
        script = MagicMock(return_value=True)
        mount = MagicMock(return_value=True)
        watchdog = MagicMock()
        m._DirectMountManager__generate_vchan_script = script
        m._DirectMountManager__mount = mount
        m._DirectMountManager__start_watchdog = watchdog
        m._DirectMountManager__do_work()
        script.assert_called_once()
        mount.assert_called_once()
        self.assertTrue(m._DirectMountManager__mounted)
        watchdog.assert_called_once()

    def test_ready_without_mode_does_not_mount(self):
        m = self._setup(ComponentState.READY, mode=None)
        mount = MagicMock()
        m._DirectMountManager__mount = mount
        m._DirectMountManager__do_work()
        mount.assert_not_called()
        self.assertFalse(m._DirectMountManager__mounted)

    def test_starting_does_not_mount(self):
        m = self._setup(ComponentState.STARTING, mode=MountMode.RW)
        mount = MagicMock()
        m._DirectMountManager__mount = mount
        m._DirectMountManager__do_work()
        mount.assert_not_called()

    def test_already_mounted_does_not_remount(self):
        m = self._setup(ComponentState.READY, mode=MountMode.RW, mounted=True)
        mount = MagicMock()
        m._DirectMountManager__mount = mount
        m._DirectMountManager__do_work()
        mount.assert_not_called()

    def test_mount_failure_stays_unmounted(self):
        m = self._setup(ComponentState.READY, mode=MountMode.RW)
        m._DirectMountManager__generate_vchan_script = MagicMock(return_value=True)
        m._DirectMountManager__mount = MagicMock(return_value=False)
        watchdog = MagicMock()
        m._DirectMountManager__start_watchdog = watchdog
        m._DirectMountManager__do_work()
        self.assertFalse(m._DirectMountManager__mounted)
        watchdog.assert_not_called()


class TestWatchdog(DirectMountManagerBase):
    def _setup(self, state, running=True, disabled=False, mounted=True):
        m = self.manager
        m._DirectMountManager__running = running
        m._DirectMountManager__disabled = disabled
        m._DirectMountManager__component_state = state
        m._DirectMountManager__mounted = mounted
        proc = MagicMock()
        m._DirectMountManager__sshfs_process = proc
        m._DirectMountManager__work_event.clear()
        return m, proc

    def test_remount_triggered_on_death(self):
        m, proc = self._setup(ComponentState.READY)
        m._DirectMountManager__watchdog()
        proc.wait.assert_called_once()
        self.assertFalse(m._DirectMountManager__mounted)
        self.assertTrue(m._DirectMountManager__work_event.is_set())

    def test_no_remount_when_off(self):
        m, proc = self._setup(ComponentState.OFF)
        m._DirectMountManager__watchdog()
        proc.wait.assert_called_once()
        self.assertTrue(m._DirectMountManager__mounted)
        self.assertFalse(m._DirectMountManager__work_event.is_set())

    def test_no_remount_when_disabled(self):
        m, proc = self._setup(ComponentState.READY, disabled=True)
        m._DirectMountManager__watchdog()
        self.assertTrue(m._DirectMountManager__mounted)
        self.assertFalse(m._DirectMountManager__work_event.is_set())

    def test_no_remount_when_stopped(self):
        m, proc = self._setup(ComponentState.READY, running=False)
        m._DirectMountManager__watchdog()
        self.assertFalse(m._DirectMountManager__work_event.is_set())

    def test_no_process_is_noop(self):
        m = self.manager
        m._DirectMountManager__work_event.clear()
        m._DirectMountManager__watchdog()
        self.assertFalse(m._DirectMountManager__work_event.is_set())


class TestSshfsOpts(DirectMountManagerBase):
    def _opts(self, mode):
        self.manager._DirectMountManager__mount_mode = mode
        return self.manager._DirectMountManager__sshfs_opts()

    def test_base_options(self):
        opts = self._opts(MountMode.RW)
        self.assertTrue(opts.startswith(f"ssh_command={dmm.VCHAN_SFTP_SCRIPT_PATH},"))
        for expected in (
            "noexec",
            "nosuid",
            "nodev",
            "default_permissions",
            "max_read=131072",
            "reconnect",
        ):
            self.assertIn(expected, opts.split(","))

    def test_rw_has_no_ro(self):
        self.assertNotIn("ro", self._opts(MountMode.RW).split(","))

    def test_ro_appends_ro(self):
        opts = self._opts(MountMode.RO)
        self.assertEqual(opts.split(",")[-1], "ro")

    def test_unknown_mode_has_no_ro(self):
        self.assertNotIn("ro", self._opts(None).split(","))


class TestGenerateVchanScript(DirectMountManagerBase):
    def test_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = str(Path(tmp) / "vchan-sftp")
            with patch.object(dmm, "VCHAN_SFTP_SCRIPT_PATH", script):
                self.assertTrue(
                    self.manager._DirectMountManager__generate_vchan_script()
                )
            content = Path(script).read_text()
            # The peer domid is resolved at runtime (survives domid changes)
            self.assertIn("xenstore-read /local/domain/system/domids/sys-usb", content)
            # The vchan data lives in the shared xenstore namespace
            self.assertIn("/local/domain/system/vchan/$(hostname)/sftp", content)
            # The Dom0-private namespace must not be used
            self.assertNotIn("/local/domain/0", content)
            self.assertTrue(os.access(script, os.X_OK))

    def test_os_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A regular file where the parent directory should be
            blocker = Path(tmp) / "blocker"
            blocker.write_text("x")
            script = str(blocker / "vchan-sftp")
            with patch.object(dmm, "VCHAN_SFTP_SCRIPT_PATH", script):
                self.assertFalse(
                    self.manager._DirectMountManager__generate_vchan_script()
                )


class TestMount(DirectMountManagerBase):
    def test_success(self):
        m = self.manager
        m._DirectMountManager__mount_mode = MountMode.RW
        proc = MagicMock()
        proc.poll.return_value = None
        with (
            patch.object(dmm.subprocess, "Popen", return_value=proc) as popen,
            patch.object(dmm.time, "sleep"),
            patch.object(dmm.os, "makedirs"),
        ):
            self.assertTrue(m._DirectMountManager__mount())
        self.assertIs(m._DirectMountManager__sshfs_process, proc)
        args = popen.call_args.args[0]
        self.assertEqual(args[0], "sshfs")
        opts = args[args.index("-o") + 1]
        self.assertEqual(opts, m._DirectMountManager__sshfs_opts())
        self.assertEqual(args[-1], Constants.USB_MOUNT_POINT)

    def test_early_exit_fails(self):
        m = self.manager
        m._DirectMountManager__mount_mode = MountMode.RW
        proc = MagicMock()
        proc.poll.return_value = 1
        proc.returncode = 1
        with (
            patch.object(dmm.subprocess, "Popen", return_value=proc),
            patch.object(dmm.time, "sleep"),
            patch.object(dmm.os, "makedirs"),
        ):
            self.assertFalse(m._DirectMountManager__mount())
        self.assertIsNone(m._DirectMountManager__sshfs_process)

    def test_popen_error_fails(self):
        m = self.manager
        m._DirectMountManager__mount_mode = MountMode.RW
        with (
            patch.object(dmm.subprocess, "Popen", side_effect=FileNotFoundError),
            patch.object(dmm.os, "makedirs"),
        ):
            self.assertFalse(m._DirectMountManager__mount())
        self.assertIsNone(m._DirectMountManager__sshfs_process)

    def test_mount_point_error_fails(self):
        m = self.manager
        m._DirectMountManager__mount_mode = MountMode.RW
        with patch.object(dmm.os, "makedirs", side_effect=OSError("nope")):
            self.assertFalse(m._DirectMountManager__mount())
        self.assertIsNone(m._DirectMountManager__sshfs_process)


class TestUnmount(DirectMountManagerBase):
    def test_with_process(self):
        m = self.manager
        m._DirectMountManager__mounted = True
        proc = MagicMock()
        m._DirectMountManager__sshfs_process = proc
        with patch.object(dmm.subprocess, "run") as run:
            m._DirectMountManager__unmount_mount()
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()
        self.assertIsNone(m._DirectMountManager__sshfs_process)
        self.assertFalse(m.is_mounted())
        self.assertEqual(run.call_args.args[0][0], "fusermount")

    def test_without_process(self):
        m = self.manager
        m._DirectMountManager__mounted = True
        with patch.object(dmm.subprocess, "run") as run:
            m._DirectMountManager__unmount_mount()
        self.assertFalse(m.is_mounted())
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][0], "fusermount")

    def test_fusermount_fallback_to_umount(self):
        m = self.manager
        with patch.object(
            dmm.subprocess,
            "run",
            side_effect=[subprocess.SubprocessError(1, ["fusermount"]), MagicMock()],
        ) as run:
            m._DirectMountManager__unmount()
        self.assertEqual(run.call_args_list[0].args[0][0], "fusermount")
        self.assertEqual(run.call_args_list[1].args[0][0], "umount")


class TestStop(DirectMountManagerBase):
    def test_stop_unmounts_and_shuts_down(self):
        m = self.manager
        m._DirectMountManager__running = True
        m._DirectMountManager__mounted = True
        proc = MagicMock()
        m._DirectMountManager__sshfs_process = proc
        with patch.object(dmm.subprocess, "run"):
            m.stop()
        self.assertFalse(m._DirectMountManager__running)
        self.assertFalse(m.is_mounted())
        proc.terminate.assert_called_once()
        self.api.stop.assert_called_once()
        self.assertTrue(m._DirectMountManager__work_event.is_set())

    def test_stop_api_failure_is_swallowed(self):
        m = self.manager
        self.api.stop.side_effect = RuntimeError("broker gone")
        with patch.object(dmm.subprocess, "run"):
            m.stop()  # must not raise

    def test_stop_when_not_mounted(self):
        m = self.manager
        with patch.object(dmm.subprocess, "run"):
            m.stop()
        self.assertFalse(m.is_mounted())


class TestOnMessageRouting(DirectMountManagerBase):
    @patch("safecor._direct_mount_manager.System")
    def test_routes_my_config_response(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        self.manager._DirectMountManager__on_message(
            f"{Topics.MY_CONFIG}/response",
            {"domains": [{"name": DOMAIN, "direct_mount": {"mode": "ro"}}]},
        )
        self.assertEqual(self.manager._DirectMountManager__mount_mode, MountMode.RO)

    def test_routes_components_response(self):
        self.manager._DirectMountManager__on_message(
            f"{Topics.DISCOVER_COMPONENTS}/response",
            components_payload(ComponentState.READY),
        )
        self.assertEqual(
            self.manager._DirectMountManager__component_state, ComponentState.READY
        )

    def test_ignores_other_topics(self):
        self.manager._DirectMountManager__on_message(
            f"{Topics.LIST_DISKS}/response", {"disks": []}
        )
        self.assertFalse(self.manager._DirectMountManager__work_event.is_set())
        self.assertEqual(
            self.manager._DirectMountManager__component_state, ComponentState.UNKNOWN
        )


class TestOnReadyAndQuery(DirectMountManagerBase):
    def test_on_ready_subscribes_and_queries(self):
        m = self.manager
        query = MagicMock()
        m._DirectMountManager__query_my_config = query
        m._DirectMountManager__on_ready()
        topics = [c.args[0] for c in self.api.subscribe.call_args_list]
        self.assertIn(f"{Topics.MY_CONFIG}/response", topics)
        self.assertIn(f"{Topics.DISCOVER_COMPONENTS}/response", topics)
        self.api.discover_components.assert_called_once()
        query.assert_called_once()

    def test_on_ready_skips_query_when_mode_known(self):
        m = self.manager
        m._DirectMountManager__mount_mode = MountMode.RW
        query = MagicMock()
        m._DirectMountManager__query_my_config = query
        m._DirectMountManager__on_ready()
        query.assert_not_called()

    @patch("safecor._direct_mount_manager.System")
    def test_on_ready_skips_query_when_disabled(self, mock_system):
        m = self.manager
        m._DirectMountManager__disabled = True
        query = MagicMock()
        m._DirectMountManager__query_my_config = query
        m._DirectMountManager__on_ready()
        query.assert_not_called()

    @patch("safecor._direct_mount_manager.System")
    def test_query_my_config_publishes_and_starts_watcher(self, mock_system):
        mock_system.domain_name.return_value = DOMAIN
        m = self.manager
        m._DirectMountManager__my_config_event.set()  # the query clears it
        started = threading.Event()
        m._DirectMountManager__watch_my_config = lambda: started.set()
        m._DirectMountManager__query_my_config()
        topic, payload = self.api.publish.call_args.args
        self.assertEqual(topic, f"{Topics.MY_CONFIG}/request")
        self.assertEqual(payload, {"domain_name": DOMAIN})
        self.assertFalse(m._DirectMountManager__my_config_event.is_set())
        self.assertTrue(started.wait(timeout=2))


if __name__ == "__main__":
    unittest.main()
