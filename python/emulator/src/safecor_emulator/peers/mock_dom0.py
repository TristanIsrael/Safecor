"""Mock Dom0 controller

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from pathlib import Path
from threading import Event

from safecor import (
    ConnectionType,
    Constants,
    MqttClient,
    NotificationFactory,
    ResponseFactory,
    System,
    Topics,
)

from ..events import EventBus


class MockDom0Controller:
    def __init__(
        self,
        sync_lock: Event,
        client_id_suffix: str = "",
        event_bus: EventBus | None = None,
    ):
        self.__sync_lock = sync_lock
        self.__mqtt_client = MqttClient(
            f"Dom0{client_id_suffix}", ConnectionType.TCP_DEBUG, "localhost"
        )
        self.__storage_path = "/tmp"
        self.__energy_level: float = 100.0
        self.__plugged: bool = True
        self.__default_language: str = "en"
        self.__restarted_domains: list[str] = []
        self.__event_bus = event_bus

    # --- event bus helpers ---------------------------------------------------
    def __emit(self, stream: str, text: str, payload: dict | None = None):
        if self.__event_bus is not None:
            self.__event_bus.publish(stream, "Dom0", text, payload)

    def __publish(self, topic: str, payload: dict):
        self.__emit("mqtt_events", f"Dom0 -> {topic}", payload)
        self.__mqtt_client.publish(topic, payload)

    def __log(self, message: str):
        self.__emit("platform_log", message)
        print(f"[Dom0] {message}")

    # --- configurable state --------------------------------------------------
    @property
    def energy_level(self) -> float:
        """Current emulated battery level (0.0 to 100.0)."""
        return self.__energy_level

    @energy_level.setter
    def energy_level(self, value: float):
        self.__energy_level = max(0.0, min(100.0, value))

    @property
    def plugged(self) -> bool:
        """Whether the emulated system is on AC power."""
        return self.__plugged

    @plugged.setter
    def plugged(self, value: bool):
        self.__plugged = value

    @property
    def default_language(self) -> str:
        """Current emulated default language code."""
        return self.__default_language

    @default_language.setter
    def default_language(self, value: str):
        self.__default_language = value

    @property
    def restarted_domains(self) -> list[str]:
        """List of domain names that have been restarted since boot."""
        return list(self.__restarted_domains)

    def record_restart(self, domain_name: str):
        """Record a domain restart (used by the scenario API)."""
        self.__restarted_domains.append(domain_name)

    # --- lifecycle -----------------------------------------------------------
    def start(self, storage_path: str):
        """Start the MQTT client and subscribe to Dom0 command topics.

        :param storage_path: local directory that emulates the Dom0 repository.
        """
        self.__storage_path = storage_path
        self.__mqtt_client.on_connected = self.__on_mqtt_connected
        self.__mqtt_client.on_message = self.__on_mqtt_message
        self.__mqtt_client.start()

    def stop(self):
        """Stop the underlying MQTT client."""
        try:
            self.__mqtt_client.stop()
        except Exception:
            pass

    def __on_mqtt_connected(self):
        self.__log("MQTT client connected")
        self.__mqtt_client.subscribe(f"{Topics.DELETE_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.SYSTEM_INFO}/request")
        self.__mqtt_client.subscribe(f"{Topics.ENERGY_STATE}/request")
        self.__mqtt_client.subscribe(f"{Topics.DEFAULT_LANGUAGE}/request")
        self.__mqtt_client.subscribe(f"{Topics.RESTART_DOMAIN}/request")
        self.__mqtt_client.subscribe(f"{Topics.SHUTDOWN}/request")
        self.__mqtt_client.subscribe(Topics.GUI_READY)
        self.__mqtt_client.subscribe(f"{Topics.SWITCH_GUI}/request")
        self.__mqtt_client.subscribe(f"{Topics.PING}/request")
        self.__mqtt_client.subscribe(f"{Topics.REPOSITORY_PATH}/request")
        self.__sync_lock.set()

    def __on_mqtt_message(self, topic: str, payload: dict):
        self.__emit("mqtt_events", f"Dom0 <- {topic}", payload)
        if topic == f"{Topics.DELETE_FILE}/request":
            self.__handle_delete_file(payload)
        elif topic == f"{Topics.SYSTEM_INFO}/request":
            self.__handle_system_info()
        elif topic == f"{Topics.ENERGY_STATE}/request":
            self.__handle_energy_state()
        elif topic == f"{Topics.DEFAULT_LANGUAGE}/request":
            self.__handle_default_language()
        elif topic == f"{Topics.RESTART_DOMAIN}/request":
            self.__handle_restart_domain(payload)
        elif topic == f"{Topics.SHUTDOWN}/request":
            self.__handle_shutdown(payload)
        elif topic == Topics.GUI_READY:
            self.__handle_gui_ready(payload)
        elif topic == f"{Topics.SWITCH_GUI}/request":
            self.__handle_switch_gui(payload)
        elif topic == f"{Topics.PING}/request":
            self.__handle_ping(payload)
        elif topic == f"{Topics.REPOSITORY_PATH}/request":
            self.__handle_repository_path()

    # --- command handlers ----------------------------------------------------
    def __handle_delete_file(self, payload: dict):
        disk = payload.get("disk", "")
        if disk != Constants.STR_REPOSITORY:
            return

        filepath = payload.get("filepath", "")
        if filepath == "":
            return

        storage_filepath = f"{self.__storage_path}/{filepath}"
        path = Path(storage_filepath)

        if not Path.exists(path):
            self.__log(f"ERROR: the file {storage_filepath} does not exist")
            return

        try:
            path.unlink()
            notif = NotificationFactory.create_notification_deleted_file(disk, filepath)
            self.__publish(Topics.DELETED_FILE, notif)
        except Exception:
            self.__log(f"The file {filepath} could not be deleted from the repository")

    def __handle_system_info(self):
        payload = System.get_system_information()
        self.__publish(f"{Topics.SYSTEM_INFO}/response", payload)

    def __handle_energy_state(self):
        payload = {
            "battery_level": round(self.__energy_level, 2),
            "plugged": 1 if self.__plugged else 0,
        }
        self.__publish(f"{Topics.ENERGY_STATE}/response", payload)

    def __handle_default_language(self):
        payload = ResponseFactory.create_response_language_default(
            self.__default_language
        )
        self.__publish(f"{Topics.DEFAULT_LANGUAGE}/response", payload)

    def __handle_restart_domain(self, payload: dict):
        domain_name = payload.get("domain_name", "")
        if not domain_name:
            return
        self.__restarted_domains.append(domain_name)
        response = ResponseFactory.create_response_restart_domain(domain_name, True, "")
        self.__publish(f"{Topics.RESTART_DOMAIN}/response", response)

    def __handle_ping(self, payload: dict):
        response = ResponseFactory.create_response_ping(
            payload.get("id", ""),
            "Dom0",
            payload.get("data", ""),
            payload.get("sent_at", ""),
        )
        self.__publish(f"{Topics.PING}/response", response)

    def __handle_repository_path(self):
        payload = {"path": self.__storage_path}
        self.__publish(f"{Topics.REPOSITORY_PATH}/response", payload)

    # --- workflow / GUI fakes (W2, W4, W5) ------------------------------------
    def request_shutdown(self, payload: dict | None = None) -> dict:
        """W2 fake: record a shutdown request and accept it (no real poweroff)."""
        payload = payload or {}
        self.__log("System shutdown requested (W2, emulated: no poweroff)")
        response = ResponseFactory.create_response_shutdown(True)
        self.__publish(f"{Topics.SHUTDOWN}/response", response)
        return response

    def notify_gui_ready(self, payload: dict | None = None) -> dict:
        """W4 fake: record the GUI-ready notification and accept it (no splash)."""
        payload = payload or {}
        self.__log("GUI ready (W4, emulated: no splash screen change)")
        response = {"accepted": True}
        self.__publish(f"{Topics.GUI_READY}/response", response)
        return response

    def request_switch_gui(self, domain: str, payload: dict | None = None) -> dict:
        """W5 fake: record a GUI switch request and accept it (no real switch)."""
        payload = dict(payload or {})
        payload.setdefault("domain", domain)
        self.__log(f"Switch GUI to {domain} (W5, emulated: no real switch)")
        response = ResponseFactory.create_response_switch_gui(True, "")
        self.__publish(f"{Topics.SWITCH_GUI}/response", response)
        return response

    def __handle_shutdown(self, payload: dict):
        self.request_shutdown(payload)

    def __handle_gui_ready(self, payload: dict):
        self.notify_gui_ready(payload)

    def __handle_switch_gui(self, payload: dict):
        self.request_switch_gui(payload.get("domain", ""), payload)
