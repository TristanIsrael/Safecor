"""Safecor emulation and testing infrastructure.

This package lets you run Safecor, and any Safecor-based product, on a
machine that has no Xen, no HVM and no real hardware. It provides:

- :class:`SystemProfile` / :func:`load_profile` -- the hardware/OS
  characteristics used to drive the fakes.
- :func:`install_fakes` / :func:`uninstall_fakes` -- the OS/hardware fakes,
  installed from the outside (the ``safecor`` library is left untouched).
- :class:`MosquittoBroker` -- a local Mosquitto broker managed for the test.
- :class:`FakeInputDevice` -- produces keyboard/mouse events in the XenBus wire
  format (for input injection without real devices).
- :class:`Emulator` -- the orchestrator that brings up the broker + the mock
  core domains (Dom0 + sys-usb) + the fakes. Use it as a context manager in
  tests, or run the ``safecor-emulator`` command to start it standalone. It
  supports USB hot-plug (:meth:`Emulator.attach_disk` / :meth:`Emulator.detach_disk`)
  and input injection (:meth:`Emulator.inject_key` / :meth:`Emulator.mouse_click`).
"""

from .profile import SystemProfile, default_profile, load_profile
from .activate import install_fakes, uninstall_fakes
from .broker import MosquittoBroker, broker_is_reachable
from .fake_input import FakeInputDevice
from .emulator import Emulator

__version__ = "0.1.0"

__all__ = [
    "SystemProfile",
    "default_profile",
    "load_profile",
    "install_fakes",
    "uninstall_fakes",
    "MosquittoBroker",
    "broker_is_reachable",
    "FakeInputDevice",
    "Emulator",
]
