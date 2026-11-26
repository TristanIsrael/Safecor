"""Tests for the vchan-tunnel-manager pure functions.

These exercise ``resolve_live_domid``, ``should_write_back``,
``list_domain_names`` and ``get_domid`` from the Dom0-side
``create-vchan-tunnels.py`` script, which resolves and self-heals the domid
cache through the ``safecor`` library's ``XenStore`` class (no CLI
subprocesses, ADR 0006).

The script is not a package, so we load it dynamically via
``importlib.util.spec_from_file_location``.  On machines without Xen, the
module-level ``conftest.py`` installs a pure-Python stub of the ``xen``
bindings so the script's ``from safecor import XenStore`` import succeeds.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import importlib.util
import os
import unittest

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

list_domain_names = _MODULE.list_domain_names
get_domid = _MODULE.get_domid
resolve_live_domid = _MODULE.resolve_live_domid
should_write_back = _MODULE.should_write_back
DOMIDS_PATH = _MODULE.XENSTORE_DOMIDS_PATH


class FakeStore:
    """In-memory fake of the ``XenStore`` class used by the script."""

    def __init__(self, tree=None, fail_children=False, fail_write=False):
        self.tree = tree or {}
        self.fail_children = fail_children
        self.fail_write = fail_write
        self.writes = []

    def read_path(self, path):
        return self.tree.get(path)

    def read_children(self, path):
        if self.fail_children:
            raise OSError("fake xenstore connection lost")
        prefix = path.rstrip("/") + "/"
        children = {
            key[len(prefix) :].split("/", 1)[0]
            for key in self.tree
            if key.startswith(prefix)
        }
        return sorted(children)

    def write(self, domain_name, key, value):
        self.writes.append((domain_name, key, value))
        if self.fail_write:
            return False
        self.tree[f"/local/domain/{domain_name}/{key}"] = value
        return True


def _store_with_domains(domids, cache=None):
    """Builds a fake store: ``/local/domain/<N>/name`` + the domid cache."""
    tree = {}
    for domid, name in domids.items():
        tree[f"/local/domain/{domid}/name"] = name
    for name, domid in (cache or {}).items():
        tree[f"{DOMIDS_PATH}/{name}"] = domid
    return FakeStore(tree)


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


class TestListDomainNames(unittest.TestCase):
    """List domain names from the domid cache (XenStore read_children)."""

    def test_success(self):
        store = _store_with_domains({}, cache={"sys-usb": "1", "app1": "2"})
        self.assertEqual(list_domain_names(store), ["app1", "sys-usb"])

    def test_empty(self):
        self.assertEqual(list_domain_names(FakeStore({})), [])

    def test_connection_lost_propagates(self):
        # The caller (the discovery loop) catches and retries.
        store = FakeStore(fail_children=True)
        with self.assertRaises(OSError):
            list_domain_names(store)


class TestGetDomid(unittest.TestCase):
    """Read the cached domid (XenStore read_path)."""

    def test_found(self):
        store = _store_with_domains({}, cache={"sys-usb": "3"})
        self.assertEqual(get_domid("sys-usb", store), "3")

    def test_absent(self):
        self.assertEqual(get_domid("nonexistent", FakeStore({})), "")

    def test_whitespace_stripped(self):
        store = _store_with_domains({}, cache={"sys-usb": "3\n"})
        self.assertEqual(get_domid("sys-usb", store), "3")


class TestResolveLiveDomid(unittest.TestCase):
    """Resolve the live domid from /local/domain/<N>/name (ADR 0006)."""

    def test_resolves_live_domid(self):
        """The scan finds the live domid; a correct cache is left alone."""
        store = _store_with_domains(
            {"0": "Dom0", "3": "sys-usb", "4": "sys-gui"},
            cache={"sys-usb": "3"},
        )
        self.assertEqual(resolve_live_domid("sys-usb", store), "3")
        self.assertEqual(store.writes, [])

    def test_no_match(self):
        """Domain not found in the scan → empty string."""
        store = _store_with_domains({"0": "Dom0", "3": "sys-usb"})
        self.assertEqual(resolve_live_domid("nonexistent", store), "")

    def test_write_back_on_difference(self):
        """Cache is written when the resolved domid differs from cached."""
        store = _store_with_domains(
            {"0": "Dom0", "3": "sys-usb"}, cache={"sys-usb": "1"}
        )
        self.assertEqual(resolve_live_domid("sys-usb", store), "3")
        self.assertEqual(store.writes, [("system", "domids/sys-usb", "3")])

    def test_no_write_back_without_cached_value(self):
        """No cached value yet → nothing to diff against, no write."""
        store = _store_with_domains({"0": "Dom0", "3": "sys-usb"}, cache={})
        self.assertEqual(resolve_live_domid("sys-usb", store), "3")
        self.assertEqual(store.writes, [])

    def test_write_failure_does_not_raise(self):
        """A failed write must not break the resolution."""
        store = _store_with_domains(
            {"0": "Dom0", "3": "sys-usb"}, cache={"sys-usb": "1"}
        )
        store.fail_write = True
        self.assertEqual(resolve_live_domid("sys-usb", store), "3")

    def test_connection_lost_returns_empty(self):
        """If the enumeration fails, return empty string."""
        store = FakeStore(fail_children=True)
        self.assertEqual(resolve_live_domid("sys-usb", store), "")


if __name__ == "__main__":
    unittest.main()
