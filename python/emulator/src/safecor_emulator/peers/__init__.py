"""Mock peer domains provided by the emulator.

These stand in for the core Domains (Dom0 and sys-usb) when running Safecor or
a Safecor-based product on a machine without Xen. They speak the same MQTT
protocol as the real controllers but operate on local directories instead of
real hardware.
"""

from .mock_dom0 import MockDom0Controller
from .mock_sys_usb import MockSysUsbController

__all__ = ["MockDom0Controller", "MockSysUsbController"]
