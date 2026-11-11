""" Mock peer domains provided by the emulator

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from .mock_dom0 import MockDom0Controller
from .mock_sys_usb import MockSysUsbController

__all__ = ["MockDom0Controller", "MockSysUsbController"]
