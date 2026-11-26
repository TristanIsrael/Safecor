"""Unit tests for the XenStore class.

The Xen Python bindings (``xen.lowlevel.xs``) are only available where Xen
is installed (Dom0 / DomUs).  When they are missing, an in-memory stub is
injected in ``sys.modules`` so the class can be imported, and every test
patches ``_xenstore.xapi`` with an in-memory fake implementing the small
API surface used by the class (``xs``, ``read``, ``read_dir``, ``write``,
``transaction_start``/``transaction_end``, ``watch``, ``read_watch``).

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import sys
import threading
import time
import types
import unittest
from unittest import mock

# Make ``import xen.lowlevel.xs`` succeed when the real bindings are not
# installed (dev machines without Xen): the per-test patch of
# ``_xenstore.xapi`` never uses this stub, it only satisfies the module
# import.  (Same pattern as MOCK_LIBVIRT for the libvirt helper tests.)
try:
    import xen.lowlevel.xs  # noqa: F401
except ImportError:
    _xen_pkg = types.ModuleType("xen")
    _lowlevel_pkg = types.ModuleType("xen.lowlevel")
    _xs_stub = types.ModuleType("xen.lowlevel.xs")
    _xs_stub.xs = lambda: None  # replaced per test
    _lowlevel_pkg.xs = _xs_stub
    _xen_pkg.lowlevel = _lowlevel_pkg
    sys.modules["xen"] = _xen_pkg
    sys.modules["xen.lowlevel"] = _lowlevel_pkg
    sys.modules["xen.lowlevel.xs"] = _xs_stub

import safecor._xenstore as xs_mod  # noqa: E402


class FakeXS:
    """In-memory fake of a ``xen.lowlevel.xs.xs()`` handle."""

    def __init__(self):
        self.tree = {}
        self.watches = {}
        self.events = []
        self.fail_write = False
        self.read_watch_count = 0

    def transaction_start(self):
        return 1

    def transaction_end(self, txn, abort=False):
        return 0

    def read(self, txn, path):
        val = self.tree.get(path)
        return None if val is None else val.encode()

    def read_dir(self, txn, path):
        prefix = path.rstrip("/") + "/"
        children = {
            key[len(prefix) :].split("/", 1)[0]
            for key in self.tree
            if key.startswith(prefix)
        }
        return sorted(children) or None

    def write(self, txn, path, value):
        if "//" in path:
            raise OSError("invalid path")
        if self.fail_write:
            raise OSError("fake write failure")
        self.tree[path] = value

    def watch(self, path, token):
        self.watches[(path, token)] = True

    def read_watch(self):
        # Block (polling the queue) like the real read_watch until an event
        # arrives; the reader thread is a daemon.
        while True:
            if self.events:
                self.read_watch_count += 1
                return self.events.pop(0)
            time.sleep(0.01)


class XenStoreTestCase(unittest.TestCase):
    """Base class: builds a XenStore over an in-memory fake tree."""

    def setUp(self):
        self.fake = FakeXS()
        patcher = mock.patch.object(
            xs_mod, "xapi", mock.MagicMock(xs=mock.MagicMock(return_value=self.fake))
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.xs = xs_mod.XenStore()

    def _wait_for_event(self, event, timeout=2.0):
        self.assertTrue(event.wait(timeout), "monitor callback not fired in time")


class TestReadPath(XenStoreTestCase):
    """read_path: raw absolute-path reads."""

    def test_read_path_present(self):
        self.fake.tree["/local/domain/system/domids/sys-usb"] = "3"
        self.assertEqual(self.xs.read_path("/local/domain/system/domids/sys-usb"), "3")

    def test_read_path_absent(self):
        self.assertIsNone(self.xs.read_path("/local/domain/system/domids/none"))

    def test_read_path_empty_value(self):
        self.fake.tree["/local/domain/system/empty"] = ""
        self.assertEqual(self.xs.read_path("/local/domain/system/empty"), "")


class TestRead(XenStoreTestCase):
    """read: domain-resolved reads (__get_domain_id)."""

    def test_read_system_domain(self):
        self.fake.tree["/local/domain/system/screen_size"] = "1280,720"
        self.assertEqual(self.xs.read("system", "screen_size"), "1280,720")

    def test_read_domain_resolved_via_domid_cache(self):
        self.fake.tree["/local/domain/system/domids/sys-usb"] = "3"
        self.fake.tree["/local/domain/3/name"] = "sys-usb"
        self.assertEqual(self.xs.read("sys-usb", "name"), "sys-usb")

    def test_read_unknown_domain(self):
        # No cache entry → dom_id "" → invalid path → None.
        self.assertIsNone(self.xs.read("nonexistent", "name"))

    def test_read_cache_entry_not_present(self):
        # Known domain name but no cache entry yet.
        self.fake.tree["/local/domain/system/domids"] = ""
        self.assertIsNone(self.xs.read("sys-usb", "name"))


class TestWrite(XenStoreTestCase):
    """write: domain-resolved transactional writes."""

    def test_write_success(self):
        ok = self.xs.write("system", "domids/app1", "7")
        self.assertTrue(ok)
        self.assertEqual(self.fake.tree["/local/domain/system/domids/app1"], "7")

    def test_write_failure(self):
        self.fake.fail_write = True
        ok = self.xs.write("system", "domids/app1", "7")
        self.assertFalse(ok)
        self.assertNotIn("/local/domain/system/domids/app1", self.fake.tree)

    def test_write_unknown_domain(self):
        # No cache entry → invalid path → the write fails.
        ok = self.xs.write("nonexistent", "domids/app1", "7")
        self.assertFalse(ok)


class TestReadChildren(XenStoreTestCase):
    """read_children: equivalent of xenstore-ls."""

    def test_read_children(self):
        self.fake.tree["/local/domain/0/name"] = "Dom0"
        self.fake.tree["/local/domain/1/name"] = "sys-usb"
        self.fake.tree["/local/domain/system/domids/sys-usb"] = "1"
        self.assertEqual(self.xs.read_children("/local/domain"), ["0", "1", "system"])

    def test_read_children_nested(self):
        self.fake.tree["/local/domain/system/domids/sys-usb"] = "1"
        self.fake.tree["/local/domain/system/domids/app1"] = "2"
        self.assertEqual(
            self.xs.read_children("/local/domain/system/domids"), ["app1", "sys-usb"]
        )

    def test_read_children_absent(self):
        self.assertEqual(self.xs.read_children("/local/domain/42"), [])


class TestMonitor(XenStoreTestCase):
    """monitor: watch lifecycle (creation, change, deletion)."""

    def test_monitor_value_change(self):
        self.fake.tree["/local/domain/system/screen_size"] = "100,200"
        received = []
        event = threading.Event()

        def callback(value):
            received.append(value)
            event.set()

        self.xs.monitor("system", "screen_size", "tok", callback)
        # The key exists: the watch is on the key itself.
        self.assertIn(("/local/domain/system/screen_size", "tok"), self.fake.watches)

        self.fake.tree["/local/domain/system/screen_size"] = "100,300"
        self.fake.events.append(("/local/domain/system/screen_size", "tok"))
        self._wait_for_event(event)
        self.assertEqual(received, ["100,300"])
        self.xs.stop()

    def test_monitor_absent_key_fires_on_creation(self):
        # The key does not exist yet: the watch is on the parent directory.
        received = []
        event = threading.Event()

        def callback(value):
            received.append(value)
            event.set()

        self.xs.monitor("system", "domids/app1", "tok", callback)
        self.assertIn(("/local/domain/system/domids", "tok"), self.fake.watches)
        self.assertNotIn(("/local/domain/system/domids/app1", "tok"), self.fake.watches)

        # The key appears → the parent watch fires.
        self.fake.tree["/local/domain/system/domids/app1"] = "7"
        self.fake.events.append(("/local/domain/system/domids", "tok"))
        self._wait_for_event(event)
        self.assertEqual(received, ["7"])
        # Re-synchronized: the watch is now on the key itself.
        self.assertIn(("/local/domain/system/domids/app1", "tok"), self.fake.watches)
        self.xs.stop()

    def test_monitor_deleted_key_keeps_watching(self):
        self.fake.tree["/local/domain/system/debug_on"] = "1"
        received = []
        event = threading.Event()

        def callback(value):
            received.append(value)
            event.set()

        self.xs.monitor("system", "debug_on", "tok", callback)

        # The key is deleted → the callback gets None and the watch is
        # re-attached to the parent (the node's watch died with the node).
        del self.fake.tree["/local/domain/system/debug_on"]
        self.fake.events.append(("/local/domain/system/debug_on", "tok"))
        self._wait_for_event(event)
        self.assertEqual(received, [None])
        self.assertIn(("/local/domain/system", "tok"), self.fake.watches)
        # The thread is still alive (monitoring continues).
        self.assertTrue(self.xs._XenStore__can_run)
        self.xs.stop()

    def test_monitor_callback_error_keeps_thread(self):
        self.fake.tree["/local/domain/system/debug_on"] = "1"
        done = threading.Event()
        original_read_watch = self.fake.read_watch

        def counting_read_watch():
            result = original_read_watch()
            if self.fake.read_watch_count >= 2:
                done.set()
            return result

        self.fake.read_watch = counting_read_watch

        def bad_callback(value):
            raise RuntimeError("boom")

        self.xs.monitor("system", "debug_on", "tok", bad_callback)
        self.fake.events.append(("/local/domain/system/debug_on", "tok"))
        self.fake.events.append(("/local/domain/system/debug_on", "tok"))
        # A raising callback must not kill the reader thread: the second
        # event is still consumed.
        self._wait_for_event(done)
        self.xs.stop()

    def test_monitor_stop_prevents_dispatch(self):
        self.fake.tree["/local/domain/system/debug_on"] = "1"
        received = []
        self.xs.monitor("system", "debug_on", "tok", received.append)
        self.xs.stop()
        time.sleep(0.1)
        self.fake.events.append(("/local/domain/system/debug_on", "tok"))
        time.sleep(0.2)
        self.assertEqual(received, [])
