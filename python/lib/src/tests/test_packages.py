"""Unit tests for the pure functions of the Alpine package scripts.

The scripts live in setup/packages/safecor/... and are loaded with
importlib; only their pure functions (path, listener and argument
computation) are tested, so no running Safecor system is required.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[4]
CORE_PYTHON = REPO_ROOT / "setup" / "packages" / "safecor" / "safecor-core" / "python"
SYS_USB_DIR = REPO_ROOT / "setup" / "packages" / "safecor" / "safecor-sys-usb"


def load_module(name: str, path: Path):
    """Load a package script (hyphenated filename) as a Python module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCreateVchanTunnels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(
            "create_vchan_tunnels", CORE_PYTHON / "create-vchan-tunnels.py"
        )

    def test_get_socket_path_msg_is_named_by_domain(self):
        self.assertEqual(
            self.mod.get_socket_path("msg", "sys-usb"), "/tmp/mqtt-sys-usb.sock"
        )
        self.assertEqual(
            self.mod.get_socket_path("msg", "test-domain"), "/tmp/mqtt-test-domain.sock"
        )

    def test_get_socket_path_input(self):
        self.assertEqual(
            self.mod.get_socket_path("input", "sys-usb"),
            "/var/run/safecor/sys-usb-input.sock",
        )

    def test_get_socket_path_tty(self):
        self.assertEqual(
            self.mod.get_socket_path("tty", "sys-usb"),
            "/var/run/safecor/sys-usb-tty.sock",
        )

    def test_get_socket_path_unknown_channel(self):
        self.assertEqual(self.mod.get_socket_path("sftp", "sys-usb"), "")

    def test_get_vchan_path_is_in_shared_namespace(self):
        self.assertEqual(
            self.mod.get_vchan_path("sys-usb", "msg"),
            "/local/domain/system/vchan/sys-usb/msg",
        )
        self.assertEqual(
            self.mod.get_vchan_path("test-domain", "sftp"),
            "/local/domain/system/vchan/test-domain/sftp",
        )

    def test_reap_dead_servers_removes_and_reaps_exited_processes(self):
        class FakePopen:
            def __init__(self, exit_code):
                self._exit_code = exit_code
                self.waited = False

            def poll(self):
                return self._exit_code

            def wait(self):
                self.waited = True
                return self._exit_code

        exited = FakePopen(1)
        running = FakePopen(None)
        active = {("1", "msg"): exited, ("2", "msg"): running}

        removed = self.mod.reap_dead_servers(active)

        self.assertEqual(removed, [("1", "msg")])
        self.assertEqual(list(active.keys()), [("2", "msg")])
        self.assertTrue(exited.waited)
        self.assertFalse(running.waited)

    def test_reap_dead_servers_empty(self):
        self.assertEqual(self.mod.reap_dead_servers({}), [])


class TestGenerateMosquittoListeners(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(
            "generate_mosquitto_listeners",
            CORE_PYTHON / "generate-mosquitto-listeners.py",
        )

    def test_generate_listeners_one_domain(self):
        topology = SimpleNamespace(domains=[SimpleNamespace(name="sys-usb")])
        lines = self.mod.generate_listeners(topology)
        self.assertEqual(lines, ["listener 0 /tmp/mqtt-sys-usb.sock"])

    def test_generate_listeners_multiple_domains(self):
        topology = SimpleNamespace(
            domains=[
                SimpleNamespace(name="sys-usb"),
                SimpleNamespace(name="test-domain"),
            ]
        )
        lines = self.mod.generate_listeners(topology)
        self.assertEqual(
            lines,
            [
                "listener 0 /tmp/mqtt-sys-usb.sock",
                "listener 0 /tmp/mqtt-test-domain.sock",
            ],
        )

    def test_generate_listeners_empty(self):
        topology = SimpleNamespace(domains=[])
        self.assertEqual(self.mod.generate_listeners(topology), [])

    def test_write_listeners(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_file = str(Path(tmp) / "conf.d" / "safecor-listeners.conf")
            self.mod.write_listeners(output_file, ["listener 0 /tmp/mqtt-sys-usb.sock"])
            content = Path(output_file).read_text()
            self.assertIn("listener 0 /tmp/mqtt-sys-usb.sock", content)
            self.assertIn("do not edit manually", content)


class TestDoasConfFiles(unittest.TestCase):
    """Sanity checks on the doas grant files (security rule: reduce surface).

    Bug history: a missing trailing newline made doas silently drop the last
    permit (run-20 pre-check, issue #275), and a relative ``cmd`` path would
    be resolved against the caller's CWD.  Every doas conf shipped in
    safecor-core must therefore end with a newline and use absolute cmd
    paths.  And no component may keep a doas grant once it stopped using
    the CLI (the vchan tunnel manager moved to the ``XenStore`` class —
    ADR 0006 — and its grant file was removed).
    """

    CORE_CONF = REPO_ROOT / "setup" / "packages" / "safecor" / "safecor-core" / "conf"

    def test_vchan_tunnels_doas_conf_removed(self):
        """The vchan tunnels no longer need doas (XenStore class, ADR 0006)."""
        self.assertFalse(
            (self.CORE_CONF / "doas-svc-vchan-tunnels.conf").exists(),
            "doas-svc-vchan-tunnels.conf must be removed: the vchan tunnel "
            "manager now uses the XenStore class (no xenstore-write CLI).",
        )

    def test_all_doas_confs_end_with_newline(self):
        confs = sorted(self.CORE_CONF.glob("doas-*.conf"))
        self.assertTrue(confs, "no doas conf found in safecor-core/conf")
        for conf in confs:
            with self.subTest(conf=conf.name):
                data = conf.read_bytes()
                self.assertTrue(
                    data.endswith(b"\n"),
                    f"{conf.name} must end with a trailing newline (doas "
                    "silently drops the last permit otherwise)",
                )

    def test_doas_confs_use_absolute_cmd_paths(self):
        for conf in sorted(self.CORE_CONF.glob("doas-*.conf")):
            for line in conf.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                self.assertIn("cmd", parts, f"{conf.name}: line without cmd: {line}")
                cmd = parts[parts.index("cmd") + 1]
                self.assertTrue(
                    cmd.startswith("/"),
                    f"{conf.name}: cmd must be an absolute path: {line}",
                )


class TestWriteScreenInformation(unittest.TestCase):
    """The screen rotation is written through the XenStore class (NFR-4).

    The script no longer spawns the ``xenstore-write`` CLI; it calls
    ``XenStore().write("system", "screen_rotation", ...)``.  The screen size
    is written by the orchestrator's initd (a boot-time one-shot shell
    command), so it is out of scope for this Python script.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(
            "write_screen_information",
            CORE_PYTHON / "write-screen-information-to-xenstore.py",
        )

    def _run_main(self, enabled: bool, rotation: int):
        topology = SimpleNamespace(
            screen=SimpleNamespace(enabled=enabled, rotation=rotation)
        )
        with (
            mock.patch.object(self.mod, "System") as system_mock,
            mock.patch.object(self.mod, "XenStore") as xenstore_mock,
        ):
            system_mock.get_topology.return_value = topology
            self.mod.main()
        return xenstore_mock

    def test_writes_rotation_when_screen_enabled(self):
        xenstore_mock = self._run_main(enabled=True, rotation=90)
        xenstore_mock.return_value.write.assert_called_once_with(
            "system", "screen_rotation", "90"
        )

    def test_no_write_when_screen_disabled(self):
        xenstore_mock = self._run_main(enabled=False, rotation=90)
        xenstore_mock.return_value.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
