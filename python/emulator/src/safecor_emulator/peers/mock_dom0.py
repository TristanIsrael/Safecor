"""Mock Dom0 controller.

Stands in for the privileged management domain (Dom0) when running on a machine
without Xen. It answers the MQTT commands the Dom0 controller would normally
handle (file deletion from the repository, system information) and operates on
a local directory instead of the real repository.
"""

from threading import Event
from pathlib import Path

from safecor import (
    MqttClient,
    ConnectionType,
    Topics,
    Constants,
    System,
    NotificationFactory,
)


class MockDom0Controller:

    def __init__(self, sync_lock: Event, client_id_suffix: str = ""):
        self.__sync_lock = sync_lock
        self.__mqtt_client = MqttClient(f"Dom0{client_id_suffix}", ConnectionType.TCP_DEBUG, "localhost")
        self.__storage_path = "/tmp"

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
        self.__sync_lock.set()

    def __on_mqtt_message(self, topic: str, payload: dict):
        if topic == f"{Topics.DELETE_FILE}/request":
            self.__handle_delete_file(payload)
        elif topic == f"{Topics.SYSTEM_INFO}/request":
            self.__handle_system_info()

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
