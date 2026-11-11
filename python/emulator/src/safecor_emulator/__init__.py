""" Safecor emulation and testing infrastructure

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
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
