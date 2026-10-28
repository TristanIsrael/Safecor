"""Mock Dom0 controller.

Stands in for the privileged management domain (Dom0) when running on a machine
without Xen. It answers the MQTT commands the Dom0 controller would normally
handle (file deletion from the repository, system information, energy state,
default language, domain restart) and operates on a local directory instead of
the real repository.
"""

from threading import Event
from pathlib import Path
from typing import List

from safecor import (
    MqttClient,
    ConnectionType,
    Topics,
    Constants,
    System,
    NotificationFactory,
    ResponseFactory,
)


class MockDom0Controller:

    def __init__(self, sync_lock: Event, client_id_suffix: str = ""):
        self.__sync_lock = sync_lock
        self.__mqtt_client = MqttClient(f"Dom0{client_id_suffix}", ConnectionType.TCP_DEBUG, "localhost")
        self.__storage_path = "/tmp"
        self.__energy_level: float = 100.0
        self.__plugged: bool = True
        self.__default_language: str = "en"
        self.__restarted_domains: List[str] = []

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
    def restarted_domains(self) -> List[str]:
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
        print("Dom0 MQTT client connected")
        self.__mqtt_client.subscribe(f"{Topics.DELETE_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.SYSTEM_INFO}/request")
        self.__mqtt_client.subscribe(f"{Topics.ENERGY_STATE}/request")
        self.__mqtt_client.subscribe(f"{Topics.DEFAULT_LANGUAGE}/request")
        self.__mqtt_client.subscribe(f"{Topics.RESTART_DOMAIN}/request")
        self.__sync_lock.set()

    def __on_mqtt_message(self, topic: str, payload: dict):
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
            print(f"ERROR: the file {storage_filepath} does not exist")
            return

        try:
            path.unlink()
            notif = NotificationFactory.create_notification_deleted_file(disk, filepath)
            self.__mqtt_client.publish(Topics.DELETED_FILE, notif)
        except Exception:
            print(f"The file {filepath} could not be deleted from the repository")

    def __handle_system_info(self):
        payload = System.get_system_information()
        self.__mqtt_client.publish(f"{Topics.SYSTEM_INFO}/response", payload)

    def __handle_energy_state(self):
        payload = {
            "battery_level": round(self.__energy_level, 2),
            "plugged": 1 if self.__plugged else 0,
        }
        self.__mqtt_client.publish(f"{Topics.ENERGY_STATE}/response", payload)

    def __handle_default_language(self):
        payload = ResponseFactory.create_response_language_default(self.__default_language)
        self.__mqtt_client.publish(f"{Topics.DEFAULT_LANGUAGE}/response", payload)

    def __handle_restart_domain(self, payload: dict):
        domain_name = payload.get("domain_name", "")
        if not domain_name:
            return
        self.__restarted_domains.append(domain_name)
        response = ResponseFactory.create_response_restart_domain(domain_name, True, "")
        self.__mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/response", response)
