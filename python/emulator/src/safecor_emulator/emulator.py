"""Orchestrate the emulated Safecor core.

The :class:`Emulator` brings together all the pieces needed to run Safecor (or
a Safecor-based product) on a machine without Xen or real hardware:

- a Mosquitto broker (reused if one is already listening on the port, otherwise
  started and owned for the lifetime of the emulator),
- the OS/hardware fakes (installed from the outside, the ``safecor`` library is
  left untouched),
- the mock core domains (Dom0 and sys-usb), which answer the core MQTT commands
  and operate on local directories instead of real hardware.

It is meant to be used as a context manager in tests::

    from safecor_emulator import Emulator

    with Emulator(source_disks={"fake-usb": "/path/to/files"}) as em:
        # run the product / Safecor calls here
        ...

The same class powers the standalone ``safecor-emulator`` command (see
:mod:`safecor_emulator.cli`), which simply keeps the emulator running so a
product can be launched in another terminal.
"""

import os
import shutil
import tempfile
import threading
import uuid
from typing import Dict, Optional

from .profile import SystemProfile, default_profile
from .activate import install_fakes, uninstall_fakes
from .broker import MosquittoBroker, broker_is_reachable
from .fake_input import FakeInputDevice
from .peers import MockDom0Controller, MockSysUsbController


class Emulator:
    """Bring up and tear down the emulated Safecor core.

    :param profile: the :class:`SystemProfile` driving the fakes
        (defaults to :func:`default_profile`).
    :param source_disks: mapping of disk id -> root directory that the
        emulated sys-usb exposes as a source disk (where files are read from).
    :param storage_path: local directory that emulates the repository.
    :param destination_disk_path: local directory that emulates the target disk
        (where copied/created files are written to).
    :param broker_port: TCP port the emulated broker must listen on
        (default 1883, because the ``safecor`` client hard-codes it in TCP mode).
    :param host: broker host (default ``localhost``).
    :param reuse_broker: if True (default) and a broker is already listening on
        the port, reuse it instead of starting one.
    :param start_timeout: seconds to wait for the mock core domains to connect.
    """

    def __init__(self,
                 profile: Optional[SystemProfile] = None,
                 source_disks: Optional[Dict[str, str]] = None,
                 storage_path: Optional[str] = None,
                 destination_disk_path: Optional[str] = None,
                 broker_port: int = 1883,
                 host: str = "localhost",
                 reuse_broker: bool = True,
                 start_timeout: float = 10.0):
        self.profile = profile if profile is not None else default_profile()
        self.source_disks = dict(source_disks or {})
        self.storage_path = storage_path
        self.destination_disk_path = destination_disk_path
        self.broker_port = broker_port
        self.host = host
        self.reuse_broker = reuse_broker
        self.start_timeout = start_timeout

        self._own_broker = False
        self._broker: Optional[MosquittoBroker] = None
        self._dom0: Optional[MockDom0Controller] = None
        self._sys_usb: Optional[MockSysUsbController] = None
        self._dom0_lock: Optional[threading.Event] = None
        self._sys_usb_lock: Optional[threading.Event] = None
        self._started = False

        # Unique per instance: keeps peer MQTT client-ids unique so several
        # emulators can share the same broker without clashing.
        self._instance_id = uuid.uuid4().hex[:8]
        self._workdir = tempfile.mkdtemp(prefix=f"safecor_emulator_{self._instance_id}_")
        self.input = FakeInputDevice(os.path.join(self._workdir, "input.events"))

    @property
    def is_running(self) -> bool:
        """True once :meth:`start` has completed successfully."""
        return self._started

    @property
    def instance_id(self) -> str:
        """A short unique identifier for this emulator instance."""
        return self._instance_id

    @property
    def input_events_path(self) -> str:
        """Path of the file the fake input device writes its events to."""
        return self.input.path

    # --- USB hot-plug ------------------------------------------------------
    def attach_disk(self, disk_id: str, root_path: str):
        """Hot-plug a disk while running: expose it and announce it.

        The emulated sys-usb owns the disk list (shared with
        :attr:`source_disks`), so it stays in sync automatically.

        :param disk_id: id under which the disk will be known.
        :param root_path: local directory that emulates the disk's contents.
        """
        if self._sys_usb is None:
            raise RuntimeError("Emulator.start() must be called first")
        self._sys_usb.attach_disk(disk_id, root_path)

    def detach_disk(self, disk_id: str):
        """Hot-unplug a previously attached disk while running."""
        if self._sys_usb is None:
            raise RuntimeError("Emulator.start() must be called first")
        self._sys_usb.detach_disk(disk_id)

    # --- fake input --------------------------------------------------------
    def inject_key(self, key, pressed: bool = True):
        """Inject a keyboard press/release (see :class:`FakeInputDevice`)."""
        self.input.inject_key(key, pressed)

    def press_key(self, key):
        """Inject a key press."""
        self.input.press_key(key)

    def release_key(self, key):
        """Inject a key release."""
        self.input.release_key(key)

    def click(self, key):
        """Inject a full key click."""
        self.input.click(key)

    def mouse_move(self, dx: int = 0, dy: int = 0):
        """Inject a relative mouse movement."""
        self.input.mouse_move(dx, dy)

    def mouse_click(self, button="left"):
        """Inject a mouse click."""
        self.input.mouse_click(button)

    def _ensure_dirs(self):
        for path in self.source_disks.values():
            if path:
                os.makedirs(path, exist_ok=True)
        if self.storage_path:
            os.makedirs(self.storage_path, exist_ok=True)
        if self.destination_disk_path:
            os.makedirs(self.destination_disk_path, exist_ok=True)

    def start(self):
        """Start the broker (if needed), install the fakes and start the peers."""
        if self._started:
            return

        # 1. broker: reuse an existing one if possible, otherwise start our own
        if self.reuse_broker and broker_is_reachable(self.host, self.broker_port):
            self._own_broker = False
            self._broker = None
        else:
            self._broker = MosquittoBroker(port=self.broker_port, host=self.host)
            self._broker.start()
            self._own_broker = True

        # 2. OS/hardware fakes (installed from the outside, reversible)
        install_fakes(self.profile.as_dict())

        # 3. local directories that emulate the disks
        self._ensure_dirs()

        # 4. mock core domains (in-process, connected over the broker)
        self._dom0_lock = threading.Event()
        self._sys_usb_lock = threading.Event()
        suffix = f"-{self._instance_id}"

        self._dom0 = MockDom0Controller(self._dom0_lock, client_id_suffix=suffix)
        self._dom0.start(self.storage_path or "/tmp")

        self._sys_usb = MockSysUsbController(self._sys_usb_lock, client_id_suffix=suffix)
        self._sys_usb.start(self.source_disks,
                            self.storage_path or "/tmp",
                            self.destination_disk_path or "/tmp")

        # 5. wait for both peers to be connected to the broker
        ok_dom0 = self._dom0_lock.wait(self.start_timeout)
        ok_usb = self._sys_usb_lock.wait(self.start_timeout)
        if not (ok_dom0 and ok_usb):
            self.stop()
            raise RuntimeError(
                f"Mock core domains did not connect within {self.start_timeout}s "
                f"(dom0={ok_dom0}, sys-usb={ok_usb}). Is the broker reachable on "
                f"{self.host}:{self.broker_port}?")

        self._started = True

    def stop(self):
        """Stop the peers, remove the fakes and (if owned) stop the broker."""
        for peer in (self._dom0, self._sys_usb):
            if peer is not None:
                try:
                    peer.stop()
                except Exception:
                    pass
        self._dom0 = None
        self._sys_usb = None

        try:
            uninstall_fakes()
        except Exception:
            pass

        if self._own_broker and self._broker is not None:
            try:
                self._broker.stop()
            except Exception:
                pass
        self._broker = None
        self._own_broker = False

        shutil.rmtree(self._workdir, ignore_errors=True)
        self._started = False

    def __enter__(self) -> "Emulator":
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False
