#!/usr/bin/env python3
"""Launcher for the DirectMountManager process.

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
