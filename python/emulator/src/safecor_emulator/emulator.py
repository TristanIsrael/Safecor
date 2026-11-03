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

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .activate import apply_dmi, install_fakes, uninstall_fakes
from .broker import MosquittoBroker, broker_is_reachable
from .events import EventBus
from .fake_input import FakeInputDevice
from .peers import MockDom0Controller, MockSysUsbController
from .profile import SystemProfile, default_profile
from .topology_env import (
    Environment,
    apply_configuration_settings,
    build_environment_from_data,
    configuration_dmi,
)


class Emulator:
    """Bring up and tear down the emulated Safecor core.

    :param profile: the :class:`SystemProfile` driving the fakes
        (defaults to :func:`default_profile`).
    :param source_disks: mapping of disk id -> root directory that the
        emulated sys-usb exposes as a source disk (where files are read from).
    :param storage_path: local directory that emulates the repository.
    :param broker_port: TCP port the emulated broker must listen on
        (default 1883, because the ``safecor`` client hard-codes it in TCP mode).
    :param host: broker host (default ``localhost``).
    :param reuse_broker: if True (default) and a broker is already listening on
        the port, reuse it instead of starting one.
    :param start_timeout: seconds to wait for the mock core domains to connect.
    :param topology_path: optional path to a product ``topology.json``. When set,
        it is served to the product under test and drives the emulated
        environment (product name, languages, screen, business Domains).
    :param configuration: optional name of one of the topology's ``configurations``
        to apply (drives the DMI fakes). ``None`` (default) applies the standard
        configuration (no hardware configuration matches).
    """

    def __init__(
        self,
        profile: Optional[SystemProfile] = None,
        source_disks: Optional[Dict[str, str]] = None,
        storage_path: Optional[str] = None,
        broker_port: int = 1883,
        host: str = "localhost",
        reuse_broker: bool = True,
        start_timeout: float = 10.0,
        topology_path: Optional[str] = None,
        configuration: Optional[str] = None,
    ):
        self.profile = profile if profile is not None else default_profile()
        self.source_disks = dict(source_disks or {})
        self.storage_path = storage_path
        self.broker_port = broker_port
        self.host = host
        self.reuse_broker = reuse_broker
        self.start_timeout = start_timeout
        self.topology_path = topology_path
        self.configuration = configuration
        self._environment: Optional[Environment] = None
        if topology_path is not None:
            self._environment = build_environment_from_data(
                json.loads(Path(topology_path).read_text(encoding="utf-8"))
            )

        self._own_broker = False
        self._broker: Optional[MosquittoBroker] = None
        self._dom0: Optional[MockDom0Controller] = None
        self._sys_usb: Optional[MockSysUsbController] = None
        self._dom0_lock: Optional[threading.Event] = None
        self._sys_usb_lock: Optional[threading.Event] = None
        self._event_bus = EventBus()
        self._started = False

        # Unique per instance: keeps peer MQTT client-ids unique so several
        # emulators can share the same broker without clashing.
        self._instance_id = uuid.uuid4().hex[:8]
        self._workdir = tempfile.mkdtemp(
            prefix=f"safecor_emulator_{self._instance_id}_"
        )
        self.input = FakeInputDevice(os.path.join(self._workdir, "input.events"))

    @property
    def is_running(self) -> bool:
        """True once :meth:`start` has completed successfully."""
        return self._started

    @property
    def owns_broker(self) -> bool:
        """True if this emulator started and owns the broker (vs. reused one)."""
        return self._own_broker

    @property
    def instance_id(self) -> str:
        """A short unique identifier for this emulator instance."""
        return self._instance_id

    @property
    def input_events_path(self) -> str:
        """Path of the file the fake input device writes its events to."""
        return self.input.path

    @property
    def environment(self) -> Optional[Environment]:
        """The :class:`Environment` derived from the topology (or ``None``)."""
        return self._environment

    @property
    def configuration_names(self) -> List[str]:
        """The ``configurations`` names declared in the topology (for the console)."""
        if self._environment is None:
            return []
        return list(self._environment.configuration_names)

    @property
    def event_bus(self) -> EventBus:
        """The :class:`~safecor_emulator.events.EventBus` shared with the mock peers."""
        return self._event_bus

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

    # --- power / energy scenarios --------------------------------------------
    def set_energy_state(self, level: float, plugged: bool = True):
        """Set the emulated energy state.

        :param level: battery level from 0.0 to 100.0.
        :param plugged: whether the system is on AC power.
        """
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        self._dom0.energy_level = level
        self._dom0.plugged = plugged

    def power_off(self):
        """Simulate a power loss (unplug + battery at 0)."""
        self.set_energy_state(0.0, plugged=False)

    def power_on(self):
        """Simulate power restore (AC plugged, full battery)."""
        self.set_energy_state(100.0, plugged=True)

    # --- domain restart scenario ---------------------------------------------
    def restart_domain(self, domain_name: str):
        """Simulate a domain restart and record it.

        The domain name is recorded in :attr:`restarted_domains`.

        :param domain_name: name of the domain to restart.
        """
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        self._dom0.record_restart(domain_name)

    @property
    def restarted_domains(self):
        """List of domain names restarted so far (for assertions)."""
        if self._dom0 is None:
            return []
        return self._dom0.restarted_domains

    # --- language -------------------------------------------------------------
    def set_default_language(self, language: str):
        """Set the emulated default language code (e.g. ``"fr"``)."""
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        self._dom0.default_language = language

    # --- workflow / GUI scenarios (W2, W4, W5) --------------------------------
    def shutdown(self):
        """Request a system shutdown (W2). The mock Dom0 records it and accepts."""
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        return self._dom0.request_shutdown()

    def gui_ready(self):
        """Notify that the GUI is ready (W4). The mock Dom0 records it and accepts."""
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        return self._dom0.notify_gui_ready()

    def switch_gui(self, domain: str):
        """Request a switch of the focused GUI domain (W5)."""
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        return self._dom0.request_switch_gui(domain)

    # --- configuration switch (runtime) ---------------------------------------
    def select_configuration(self, name: Optional[str] = None):
        """Select a hardware configuration at runtime (``None`` = standard).

        Re-serves the DMI fakes so that the next ``System.get_topology`` (after
        a ``reset_topology``) applies the chosen configuration's settings.

        :param name: the configuration ``name`` declared in the topology, or
            ``None`` / empty for the standard configuration.
        """
        if self._environment is None:
            raise RuntimeError("No topology loaded; cannot select a configuration")
        apply_dmi(configuration_dmi(self._environment, name))
        apply_configuration_settings(self._environment, name)
        self.configuration = name

    # --- connectivity ---------------------------------------------------------
    def _request_response(
        self,
        request_topic: str,
        response_topic: str,
        payload: dict,
        timeout: float = 5.0,
    ):
        """Send a one-shot request over the broker and wait for its response.

        A short-lived MQTT client is created, the request published and the
        matching response awaited. Returns the response payload, or ``None`` on
        timeout. Used by the connectivity helpers (e.g. :meth:`ping`).
        """
        from safecor import ConnectionType, MqttClient

        result: dict = {}
        connected = threading.Event()
        done = threading.Event()
        client = MqttClient(
            f"emulator-{self._instance_id}-{uuid.uuid4().hex[:6]}",
            ConnectionType.TCP_DEBUG,
            self.host,
        )

        def on_connected():
            client.subscribe(response_topic)
            connected.set()

        def on_message(topic, msg_payload):
            if topic == response_topic:
                result["response"] = msg_payload
                done.set()

        client.on_connected = on_connected
        client.on_message = on_message
        client.start()
        try:
            if not connected.wait(timeout):
                return None
            time.sleep(0.2)  # let the subscription settle
            client.publish(request_topic, payload)
            if not done.wait(timeout):
                return None
            return result.get("response")
        finally:
            try:
                client.stop()
            except Exception:
                pass

    def ping(self, target: str = "Dom0", data: str = ""):
        """Ping a domain over the broker (connectivity check).

        Sends a ``PING`` request and waits for the echo response from the mock
        Dom0. Returns the response payload, or ``None`` on timeout.
        """
        if self._dom0 is None:
            raise RuntimeError("Emulator.start() must be called first")
        from safecor import Topics

        payload = {
            "id": f"emul-{uuid.uuid4().hex[:8]}",
            "target": target,
            "data": data,
            "sent_at": time.time(),
        }
        return self._request_response(
            f"{Topics.PING}/request", f"{Topics.PING}/response", payload
        )

    def discover_components(self) -> List[Dict[str, str]]:
        """Query the peers for their components and return a flat list.

        Publishes a ``DISCOVER_COMPONENTS`` request and collects the response
        (the mock sys-usb announces its controllers). Each entry is
        ``{"name": <label>, "state": <state>}``. Returns an empty list when the
        emulator is not running or the request times out.
        """
        if self._sys_usb is None:
            return []
        from safecor import Topics

        response = self._request_response(
            f"{Topics.DISCOVER_COMPONENTS}/request",
            f"{Topics.DISCOVER_COMPONENTS}/response",
            {},
            timeout=3.0,
        )
        components: List[Dict[str, str]] = []
        if isinstance(response, dict):
            for comp in response.get("components", []):
                components.append(
                    {
                        "name": comp.get("label") or comp.get("id") or "?",
                        "state": comp.get("state", "unknown"),
                    }
                )
        return components

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
        if self._environment is not None:
            install_fakes(
                self.profile.as_dict(),
                topology_content=Path(self.topology_path).read_text(encoding="utf-8"),
                domains=self._environment.business_domain_names(),
                dmi=configuration_dmi(self._environment, self.configuration),
            )
        else:
            install_fakes(self.profile.as_dict())

        # 3. local directories that emulate the disks
        self._ensure_dirs()

        # 4. mock core domains (in-process, connected over the broker)
        self._dom0_lock = threading.Event()
        self._sys_usb_lock = threading.Event()
        suffix = f"-{self._instance_id}"

        self._dom0 = MockDom0Controller(
            self._dom0_lock, client_id_suffix=suffix, event_bus=self._event_bus
        )
        self._dom0.start(self.storage_path or "/tmp")

        self._sys_usb = MockSysUsbController(
            self._sys_usb_lock, client_id_suffix=suffix, event_bus=self._event_bus
        )
        self._sys_usb.start(
            self.source_disks,
            self.storage_path or "/tmp",
        )

        # 5. wait for both peers to be connected to the broker
        ok_dom0 = self._dom0_lock.wait(self.start_timeout)
        ok_usb = self._sys_usb_lock.wait(self.start_timeout)
        if not (ok_dom0 and ok_usb):
            self.stop()
            raise RuntimeError(
                f"Mock core domains did not connect within {self.start_timeout}s "
                f"(dom0={ok_dom0}, sys-usb={ok_usb}). Is the broker reachable on "
                f"{self.host}:{self.broker_port}?"
            )

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
