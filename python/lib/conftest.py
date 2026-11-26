"""Shared test setup for the safecor library test suite (root conftest).

Installs a pure-Python stub for the ``xen`` Python bindings when they are
not available (dev machines without Xen), so that modules importing
``xen.lowlevel.xs`` (``safecor._xenstore`` and the ``create-vchan-tunnels``
package script) can be imported and unit-tested with in-memory fakes.  On
Xen hosts (Dom0 / DomUs) the real bindings are used as-is.

This must live at the suite root (not in ``src/tests/``): importing the
test package (``src/tests/__init__.py``) already imports ``safecor``, and
package imports happen before a same-directory conftest is loaded.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import sys
import types

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
