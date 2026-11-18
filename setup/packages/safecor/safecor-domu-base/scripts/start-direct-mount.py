#!/usr/bin/env python3
"""Launcher for the DirectMountManager process.

The manager mirrors its diagnostics on standard error, so starting this
script manually in the domain console reports the failure reason. The
openrc instance (``direct-mount``) discards that output by default.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import sys

sys.path.insert(0, "/usr/lib/safecor")

from safecor import DirectMountManager

if __name__ == "__main__":
    manager = DirectMountManager()
    manager.run()
