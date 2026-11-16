"""Unit tests for the pure functions of the Alpine package scripts.

The scripts live in setup/packages/safecor/... and are loaded with
importlib; only their pure functions (path and listener computation) are
tested, so no running Safecor system is required.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[4]
CORE_PYTHON = REPO_ROOT / "setup" / "packages" / "safecor" / "safecor-core" / "python"


def load_module(name: str, filename: str):
    """Load a package script (hyphenated filename) as a Python module."""
    spec = importlib.util.spec_from_file_location(name, CORE_PYTHON / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCreateVchanTunnels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module("create_vchan_tunnels", "create-vchan-tunnels.py")

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
            "generate_mosquitto_listeners", "generate-mosquitto-listeners.py"
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


if __name__ == "__main__":
    unittest.main()
