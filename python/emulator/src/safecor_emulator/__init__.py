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

from .activate import apply_dmi, install_fakes, uninstall_fakes
from .broker import MosquittoBroker, broker_is_reachable
from .emulator import Emulator
from .events import STREAMS, Event, EventBus, FileRecorder
from .fake_input import FakeInputDevice
from .profile import SystemProfile, default_profile, load_profile
from .topology_env import (
    NO_CONFIGURATION,
    BusinessDomain,
    Environment,
    Screen,
    build_environment,
    build_environment_from_data,
    configuration_dmi,
    load_topology_data,
)

# NOTE: ``safecor_emulator.console.ConsoleController`` requires PySide6 (the
# optional ``gui`` extra) and is therefore not imported here, so the package
# stays importable without the GUI dependency.

__version__ = "0.1.0"

__all__ = [
    "SystemProfile",
    "default_profile",
    "load_profile",
    "install_fakes",
    "uninstall_fakes",
    "apply_dmi",
    "MosquittoBroker",
    "broker_is_reachable",
    "FakeInputDevice",
    "Emulator",
    "EventBus",
    "Event",
    "FileRecorder",
    "STREAMS",
    "NO_CONFIGURATION",
    "Environment",
    "BusinessDomain",
    "Screen",
    "load_topology_data",
    "build_environment",
    "build_environment_from_data",
    "configuration_dmi",
]
