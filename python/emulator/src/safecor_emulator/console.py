"""The operator console controller.

A Qt ``QObject`` that bridges the QML views and the in-process
:class:`~safecor_emulator.Emulator`. It owns the live state (running, broker,
disks, energy, language, restarted domains), observes the three event streams
(via the shared :class:`~safecor_emulator.events.EventBus`) and exposes the
scenario controls as slots.

The QML never touches the :class:`~safecor_emulator.Emulator` directly; this
controller is the single bridge (Saphir / demo2 convention).

This module requires PySide6 (the optional ``gui`` extra).
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from .emulator import Emulator
from .events import EventBus, FileRecorder


class ConsoleController(QObject):
    """QObject controller exposing the emulator state and the scenario controls.

    :param parent: optional parent QObject.
    :param emulator: an (optionally already started) :class:`Emulator` to drive.
        When omitted, :meth:`start_emulator` creates one from ``emulator_params``.
    :param emulator_params: keyword arguments forwarded to the
        :class:`Emulator` constructor when the controller must create one.
    """

    stateChanged = Signal()
    disksChanged = Signal()
    energyChanged = Signal()
    actionLogged = Signal(object)
    mqttEventLogged = Signal(object)
    logLine = Signal(str)

    def __init__(
        self,
        parent: Optional[QObject] = None,
        emulator: Optional[Emulator] = None,
        **emulator_params
    ):
        super().__init__(parent)
        self.__emulator = emulator
        self.__emulator_params = emulator_params

        self.__running = False
        self.__broker_port = 0
        self.__broker_owned = False
        self.__peers_connected: List[str] = []
        self.__environment = None
        self.__disks: List[str] = []
        self.__energy_level = 100.0
        self.__plugged = True
        self.__default_language = "en"
        self.__languages: List[str] = []
        self.__restarted_domains: List[str] = []

        self.__bus_attached: Optional[EventBus] = None
        self.__recorders: Dict[str, FileRecorder] = {}
        self.__pending_recorders: Dict[str, str] = {}

        if emulator is not None:
            self.__attach_bus(emulator.event_bus)
            self.__sync_from_emulator()

    # --- event bus wiring ----------------------------------------------------
    def __attach_bus(self, bus: Optional[EventBus]):
        if bus is self.__bus_attached:
            return
        if self.__bus_attached is not None:
            self.__bus_attached.unsubscribe("actions", self.__on_action)
            self.__bus_attached.unsubscribe("mqtt_events", self.__on_mqtt_event)
            self.__bus_attached.unsubscribe("platform_log", self.__on_log)
        self.__bus_attached = bus
        if bus is not None:
            bus.subscribe("actions", self.__on_action)
            bus.subscribe("mqtt_events", self.__on_mqtt_event)
            bus.subscribe("platform_log", self.__on_log)

    def __on_action(self, event):
        self.actionLogged.emit(event)

    def __on_mqtt_event(self, event):
        self.mqttEventLogged.emit(event)

    def __on_log(self, event):
        self.logLine.emit(event.text)

    def __record_action(self, text: str, payload: Optional[dict] = None):
        if self.__bus_attached is not None:
            self.__bus_attached.publish("actions", "console", text, payload)

    # --- state sync ----------------------------------------------------------
    def __sync_from_emulator(self):
        em = self.__emulator
        self.__running = em.is_running
        self.__broker_port = em.broker_port
        self.__broker_owned = em.owns_broker
        self.__peers_connected = ["Dom0", "sys-usb"] if em.is_running else []
        self.__environment = em.environment
        self.__languages = list(em.environment.languages) if em.environment else []
        self.__default_language = (
            em.environment.default_language if em.environment else "en"
        )
        self.__disks = list(em.source_disks.keys())
        self.__restarted_domains = list(em.restarted_domains)

    # --- control slots -------------------------------------------------------
    @Slot()
    def start_emulator(self):
        """Create (if needed) and start the emulator, then sync the state."""
        if self.__emulator is None:
            self.__emulator = Emulator(**self.__emulator_params)
        self.__emulator.start()
        self.__attach_bus(self.__emulator.event_bus)
        self.__sync_from_emulator()
        self.__energy_level = 100.0
        self.__plugged = True
        # Apply any recorders requested before the bus existed.
        for stream, path in list(self.__pending_recorders.items()):
            self.__set_stream_recorder(stream, path)
        self.__pending_recorders.clear()
        self.stateChanged.emit()
        self.disksChanged.emit()
        self.energyChanged.emit()
        self.__record_action("start_emulator", {"broker_port": self.__broker_port})

    @Slot()
    def stop_emulator(self):
        """Stop the emulator (peers, fakes, and the owned broker)."""
        if self.__emulator is not None:
            self.__emulator.stop()
            self.__sync_from_emulator()
        self.__running = False
        self.__peers_connected = []
        self.stateChanged.emit()
        self.disksChanged.emit()
        self.__record_action("stop_emulator", {})

    @Slot(str)
    def select_configuration(self, name: str):
        """Select a hardware configuration (empty string = standard)."""
        self.__require_emulator().select_configuration(name or None)
        self.__record_action("select_configuration", {"name": name})
        self.stateChanged.emit()

    @Slot(str, str)
    def attach_disk(self, disk_id: str, path: str):
        """Hot-plug a disk and announce it."""
        self.__require_emulator().attach_disk(disk_id, path)
        if disk_id not in self.__disks:
            self.__disks.append(disk_id)
        self.disksChanged.emit()
        self.__record_action("attach_disk", {"disk": disk_id, "path": path})

    @Slot(str)
    def detach_disk(self, disk_id: str):
        """Hot-unplug a previously attached disk."""
        self.__require_emulator().detach_disk(disk_id)
        if disk_id in self.__disks:
            self.__disks.remove(disk_id)
        self.disksChanged.emit()
        self.__record_action("detach_disk", {"disk": disk_id})

    @Slot(float, bool)
    def set_energy(self, level: float, plugged: bool):
        """Set the emulated battery level and AC power state."""
        self.__require_emulator().set_energy_state(level, plugged)
        self.__energy_level = level
        self.__plugged = plugged
        self.energyChanged.emit()
        self.__record_action("set_energy", {"level": level, "plugged": plugged})

    @Slot()
    def power_off(self):
        """Simulate a power loss (unplug, battery at 0)."""
        self.__require_emulator().power_off()
        self.__energy_level = 0.0
        self.__plugged = False
        self.energyChanged.emit()
        self.__record_action("power_off", {})

    @Slot()
    def power_on(self):
        """Simulate a power restore (AC plugged, full battery)."""
        self.__require_emulator().power_on()
        self.__energy_level = 100.0
        self.__plugged = True
        self.energyChanged.emit()
        self.__record_action("power_on", {})

    @Slot(str)
    def set_language(self, code: str):
        """Set the emulated default language code."""
        self.__require_emulator().set_default_language(code)
        self.__default_language = code
        self.stateChanged.emit()
        self.__record_action("set_language", {"code": code})

    @Slot(str)
    def restart_domain(self, name: str):
        """Record a domain restart (W1)."""
        em = self.__require_emulator()
        em.restart_domain(name)
        self.__restarted_domains = list(em.restarted_domains)
        self.stateChanged.emit()
        self.__record_action("restart_domain", {"name": name})

    @Slot()
    def shutdown(self):
        """Request a system shutdown (W2). Returns the (accepted) response."""
        response = self.__require_emulator().shutdown()
        self.__record_action("shutdown", response or {})
        self.stateChanged.emit()
        return response

    @Slot()
    def gui_ready(self):
        """Notify that the GUI is ready (W4). Returns the (accepted) response."""
        response = self.__require_emulator().gui_ready()
        self.__record_action("gui_ready", response or {})
        self.stateChanged.emit()
        return response

    @Slot(str)
    def switch_gui(self, domain: str):
        """Request a switch of the focused GUI domain (W5)."""
        response = self.__require_emulator().switch_gui(domain)
        self.__record_action("switch_gui", {"domain": domain, "response": response})
        self.stateChanged.emit()
        return response

    @Slot(str, str)
    def ping(self, target: str, data: str):
        """Ping a domain over the broker (connectivity check)."""
        response = self.__require_emulator().ping(target, data)
        self.__record_action("ping", {"target": target, "response": response})
        return response

    @Slot(str)
    def set_loglevel(self, level: str):
        """Change the platform log level (recorded; no real effect on the mocks)."""
        self.__record_action("set_loglevel", {"level": level})

    @Slot(str, str)
    def save_log(self, disk: str, filename: str):
        """Save the platform log to a disk (recorded; no real effect on the mocks)."""
        self.__record_action("save_log", {"disk": disk, "filename": filename})

    @Slot(str)
    def set_record_journal(self, path: str):
        """Record the ``actions`` journal to ``path`` (empty string stops it)."""
        self.__set_stream_recorder("actions", path)
        self.__record_action("set_record_journal", {"path": path})

    @Slot(str)
    def set_record_events(self, path: str):
        """Record the ``mqtt_events`` stream to ``path`` (empty string stops it)."""
        self.__set_stream_recorder("mqtt_events", path)
        self.__record_action("set_record_events", {"path": path})

    @Slot()
    def clear_actions(self):
        """Clear the ``actions`` journal."""
        if self.__bus_attached is not None:
            self.__bus_attached.clear("actions")

    # --- recording -----------------------------------------------------------
    def __set_stream_recorder(self, stream: str, path: str):
        bus = self.__bus_attached
        if bus is None:
            self.__pending_recorders[stream] = path
            return
        if stream in self.__recorders:
            bus.unsubscribe(stream, self.__recorders[stream])
            self.__recorders[stream].close()
            del self.__recorders[stream]
        if path:
            recorder = FileRecorder(path)
            self.__recorders[stream] = recorder
            bus.subscribe(stream, recorder)

    # --- helpers -------------------------------------------------------------
    def __require_emulator(self) -> Emulator:
        if self.__emulator is None:
            raise RuntimeError("No emulator; call start_emulator() first")
        return self.__emulator

    # --- getters -------------------------------------------------------------
    def __is_running(self):
        return self.__running

    def __get_broker_port(self):
        return self.__broker_port

    def __get_broker_owned(self):
        return self.__broker_owned

    def __get_peers_connected(self):
        return list(self.__peers_connected)

    def __get_environment(self):
        return self.__environment

    def __get_disks(self):
        return list(self.__disks)

    def __get_energy_level(self):
        return self.__energy_level

    def __get_plugged(self):
        return self.__plugged

    def __get_default_language(self):
        return self.__default_language

    def __get_languages(self):
        return list(self.__languages)

    def __get_restarted_domains(self):
        return list(self.__restarted_domains)

    # --- QML-visible properties ----------------------------------------------
    running = Property(bool, __is_running, notify=stateChanged)
    brokerPort = Property(int, __get_broker_port, notify=stateChanged)
    brokerOwned = Property(bool, __get_broker_owned, notify=stateChanged)
    peersConnected = Property(list, __get_peers_connected, notify=stateChanged)
    environment = Property(object, __get_environment, notify=stateChanged)
    disks = Property(list, __get_disks, notify=disksChanged)
    energyLevel = Property(float, __get_energy_level, notify=energyChanged)
    plugged = Property(bool, __get_plugged, notify=energyChanged)
    defaultLanguage = Property(str, __get_default_language, notify=stateChanged)
    languages = Property(list, __get_languages, notify=stateChanged)
    restartedDomains = Property(list, __get_restarted_domains, notify=stateChanged)
