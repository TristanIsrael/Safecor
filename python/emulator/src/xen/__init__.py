"""Pure-Python in-memory stand-in for the ``xen`` Python bindings.

The emulator needs ``import xen.lowlevel.xs`` to succeed (the ``safecor``
library's ``XenStore`` class binds against it) without Xen being installed.
This package provides a minimal in-memory implementation of the API surface
used by ``safecor._xenstore.XenStore``.  It is picked up through
``PYTHONPATH`` (``python/emulator/src``) ahead of any installed ``xen``
package.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""
