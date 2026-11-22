"""Unit tests for the pure functions of the Alpine package scripts.

The scripts live in setup/packages/safecor/... and are loaded with
importlib; only their pure functions (path, listener and argument
computation) are tested, so no running Safecor system is required.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import importlib.util
import os
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


class TestSafecorVchanSftp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(
            "safecor_vchan_sftp", SYS_USB_DIR / "safecor-vchan-sftp.py"
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
            self.mod.parse_direct_mount_domains(response),
            [("app1", "ro"), ("app2", "rw")],
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
        self.assertEqual(self.mod.parse_direct_mount_domains(response), [])

    def test_parse_direct_mount_domains_invalid_mode_defaults_to_rw(self):
        response = {"domains": [{"name": "app1", "direct_mount": {"mode": "weird"}}]}
        self.assertEqual(
            self.mod.parse_direct_mount_domains(response), [("app1", "rw")]
        )

    def test_parse_direct_mount_domains_non_dict_defaults_to_rw(self):
        response = {"domains": [{"name": "app1", "direct_mount": True}]}
        self.assertEqual(
            self.mod.parse_direct_mount_domains(response), [("app1", "rw")]
        )

    def test_parse_direct_mount_domains_empty(self):
        self.assertEqual(self.mod.parse_direct_mount_domains({}), [])
        self.assertEqual(self.mod.parse_direct_mount_domains({"domains": []}), [])

    def test_sftp_server_args_rw(self):
        self.assertEqual(self.mod.sftp_server_args("rw"), ["-u", "077"])

    def test_sftp_server_args_ro(self):
        self.assertEqual(self.mod.sftp_server_args("ro"), ["-u", "077", "-R"])

    def test_sftp_credentials(self):
        with mock.patch.object(self.mod.pwd, "getpwnam") as m:
            m.return_value = mock.Mock(pw_uid=1002, pw_gid=2000)
            self.assertEqual(self.mod.sftp_credentials(), (1002, 2000))
            m.assert_called_once_with("svc-sys-usb-sftp")

    def test_sftp_credentials_missing_account(self):
        with mock.patch.object(self.mod.pwd, "getpwnam", side_effect=KeyError):
            with self.assertRaises(KeyError):
                self.mod.sftp_credentials()

    @classmethod
    def make_context(cls):
        """A sandbox context with the Alpine 3.24 values."""
        return cls.mod.SandboxContext(
            setpriv="/bin/setpriv",
            setpriv_libs=["/usr/lib/libeconf.so.0", "/usr/lib/libcap-ng.so.0"],
            passwd="/var/run/safecor/sftp-sandbox-passwd",
        )

    def test_bwrap_args_rw(self):
        self.assertEqual(
            self.mod.bwrap_args("rw", 1002, 2000, self.make_context()),
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
                "/var/run/safecor/sftp-sandbox-passwd",
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
        self.assertEqual(
            self.mod.bwrap_args("ro", 1002, 2000, self.make_context()),
            [
                "bwrap",
                "--tmpfs",
                "/",
                "--dir",
                "/media/usb",
                "--ro-bind",
                "/media/usb",
                "/media/usb",
                "--dir",
                "/etc",
                "--ro-bind",
                "/var/run/safecor/sftp-sandbox-passwd",
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
                "-R",
            ],
        )

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
            self.mod.parse_ldd_output(output),
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
            self.mod.parse_ldd_output(output),
            ["/usr/lib/libfoo.so.0", "/lib/libc.so.0"],
        )

    def test_parse_ldd_output_empty(self):
        self.assertEqual(self.mod.parse_ldd_output(""), [])
        self.assertEqual(self.mod.parse_ldd_output("statically linked\n"), [])

    def test_setpriv_library_paths(self):
        ldd_output = (
            "\tld-linux-x86-64.so.2 => /lib/ld-musl-x86_64.so.1 (0x1)\n"
            "\tlibcap-ng.so.0 => /usr/lib/libcap-ng.so.0 (0x2)\n"
        )
        with mock.patch.object(
            self.mod.subprocess, "run", return_value=mock.Mock(stdout=ldd_output)
        ) as m:
            self.assertEqual(
                self.mod.setpriv_library_paths("/bin/setpriv"),
                ["/usr/lib/libcap-ng.so.0"],
            )
            m.assert_called_once()
            self.assertEqual(m.call_args.args[0], ["ldd", "/bin/setpriv"])

    def test_bind_dirs(self):
        self.assertEqual(
            self.mod.bind_dirs(
                ["/etc/passwd", "/usr/lib/ssh/sftp-server", "/usr/lib/libfoo.so.0"]
            ),
            ["/etc", "/usr", "/usr/lib", "/usr/lib/ssh"],
        )

    def test_bind_dirs_shallow_and_empty(self):
        self.assertEqual(self.mod.bind_dirs(["/setpriv"]), [])
        self.assertEqual(self.mod.bind_dirs([]), [])

    def test_write_sandbox_passwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "safecor" / "passwd")
            result = self.mod.write_sandbox_passwd(1002, 2000, path)
            self.assertEqual(result, path)
            self.assertEqual(
                Path(path).read_text(),
                "svc-sys-usb-sftp:x:1002:2000::/:/sbin/nologin\n",
            )
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
