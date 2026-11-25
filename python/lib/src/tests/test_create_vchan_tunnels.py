"""Tests for the vchan-tunnel-manager pure functions.

These exercise ``resolve_live_domid``, ``should_write_back``, and
``write_xenstore`` from the Dom0-side ``create-vchan-tunnels.py`` script.

The script is not a package, so we load it dynamically via
``importlib.util.spec_from_file_location``.
"""

import importlib.util
import os
import unittest
import unittest.mock as mock

# Load the script from its file path.
_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "..",
    "setup",
    "packages",
    "safecor",
    "safecor-core",
    "python",
    "create-vchan-tunnels.py",
)
_SPEC = importlib.util.spec_from_file_location("create_vchan_tunnels", _SCRIPT_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

resolve_live_domid = _MODULE.resolve_live_domid
should_write_back = _MODULE.should_write_back
write_xenstore = _MODULE.write_xenstore
read_xenstore = _MODULE.read_xenstore
list_domain_names = _MODULE.list_domain_names


class TestShouldWriteBack(unittest.TestCase):
    """Pure function: should the cache be updated?"""

    def test_different_values(self):
        self.assertTrue(should_write_back("1", "2"))

    def test_same_value(self):
        self.assertFalse(should_write_back("1", "1"))

    def test_old_is_empty(self):
        self.assertFalse(should_write_back("", "1"))

    def test_new_is_empty(self):
        self.assertFalse(should_write_back("1", ""))

    def test_both_empty(self):
        self.assertFalse(should_write_back("", ""))


class TestWriteXenstore(unittest.TestCase):
    """Write to xenstore (subprocess wrapper through doas)."""

    def test_success(self):
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(returncode=0)
            self.assertTrue(write_xenstore("/some/path", "value"))
            run.assert_called_once_with(
                ["/usr/bin/doas", "/usr/bin/xenstore-write", "/some/path", "value"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_failure(self):
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(returncode=1)
            self.assertFalse(write_xenstore("/some/path", "value"))

    def test_process_error(self):
        with mock.patch.object(
            _MODULE.subprocess, "run", side_effect=FileNotFoundError
        ):
            self.assertFalse(write_xenstore("/some/path", "value"))


class TestReadXenstore(unittest.TestCase):
    """Read from xenstore (subprocess wrapper)."""

    def test_success(self):
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(stdout="42\n")
            self.assertEqual(read_xenstore("/some/path"), "42")

    def test_error(self):
        with mock.patch.object(
            _MODULE.subprocess, "run", side_effect=FileNotFoundError
        ):
            self.assertEqual(read_xenstore("/some/path"), "")


class TestListDomainNames(unittest.TestCase):
    """List domain names from the domids cache."""

    def test_success(self):
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(stdout="sys-usb\nsys-gui\nmyapp\n")
            self.assertEqual(list_domain_names(), ["sys-usb", "sys-gui", "myapp"])

    def test_empty(self):
        """Empty stdout → strip().split() returns []."""
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(stdout="\n")
            self.assertEqual(list_domain_names(), [])

    def test_error(self):
        with mock.patch.object(
            _MODULE.subprocess, "run", side_effect=FileNotFoundError
        ):
            self.assertEqual(list_domain_names(), [])


class TestResolveLiveDomid(unittest.TestCase):
    """Resolve live domid from /local/domain/<N>/name scan (ADR 0006)."""

    def test_numeric_key_scan(self):
        """Only numeric directory names are valid domid entries."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "read_xenstore", return_value="3") as read_xen,
        ):
            run.return_value = mock.MagicMock(
                stdout="3 name:sys-usb\n4 name:sys-gui\nsystem name:test"
            )
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "3")
            read_xen.assert_called()

    def test_skip_system(self):
        """The 'system' directory (the cache itself) is not a valid domain."""
        with mock.patch.object(_MODULE.subprocess, "run") as run:
            run.return_value = mock.MagicMock(
                stdout="system name:system\ndomids name:domids"
            )
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "")

    def test_name_to_domid_mapping(self):
        """Maps domain name to correct domid."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "read_xenstore", return_value="5"),
        ):
            run.return_value = mock.MagicMock(stdout="5 name:sys-usb\n3 name:sys-gui")
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "5")

    def test_no_match(self):
        """Domain not found in the scan → empty string."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "read_xenstore", return_value=""),
        ):
            run.return_value = mock.MagicMock(stdout="3 name:sys-usb")
            result = resolve_live_domid("nonexistent")
            self.assertEqual(result, "")

    def test_malformed_lines_tolerated(self):
        """Lines that don't match the expected format are skipped."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "read_xenstore", return_value="7"),
        ):
            run.return_value = mock.MagicMock(
                stdout="garbage line\n7 name:sys-usb\nanother"
            )
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "7")

    def test_write_back_only_on_difference(self):
        """Cache is updated only when resolved domid differs from cached."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "write_xenstore") as write,
        ):
            run.return_value = mock.MagicMock(stdout="3 name:sys-usb")
            # Same value: no write.
            resolve_live_domid("sys-usb")
            write.assert_not_called()

    def test_write_back_on_difference(self):
        """Cache is written when resolved domid differs from cached."""
        read_mock = mock.MagicMock(return_value="1")
        write_mock = mock.MagicMock(return_value=True)
        old_defaults = resolve_live_domid.__defaults__
        resolve_live_domid.__defaults__ = (read_mock, write_mock)
        try:
            with mock.patch.object(_MODULE.subprocess, "run") as run:
                run.return_value = mock.MagicMock(stdout="3 name:sys-usb")
                result = resolve_live_domid("sys-usb")
                self.assertEqual(result, "3")
                write_mock.assert_called_once_with(
                    _MODULE.XENSTORE_DOMIDS_PATH + "/sys-usb", "3"
                )
        finally:
            resolve_live_domid.__defaults__ = old_defaults

    def test_write_failure_does_not_raise(self):
        """A failed xenstore-write must not break the resolution."""
        with (
            mock.patch.object(_MODULE.subprocess, "run") as run,
            mock.patch.object(_MODULE, "read_xenstore", return_value="1"),
            mock.patch.object(_MODULE, "write_xenstore", return_value=False),
        ):
            run.return_value = mock.MagicMock(stdout="3 name:sys-usb")
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "3")

    def test_process_error_returns_empty(self):
        """If xenstore-ls fails, return empty string."""
        with mock.patch.object(
            _MODULE.subprocess, "run", side_effect=FileNotFoundError
        ):
            result = resolve_live_domid("sys-usb")
            self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
