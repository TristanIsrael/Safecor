from safecor import Api, Topics, Constants, MqttClient, ConnectionType, System, NotificationFactory
from pathlib import Path
from threading import Event

class MockDom0Controller:

    def __init__(self, verrou:Event):
        self.__mqtt_client = MqttClient("Dom0", ConnectionType.TCP_DEBUG, "localhost")
        self.__verrou = verrou
        self.__storage_path = "/tmp"

    def start(self, storage_path):
        self.__storage_path = storage_path
        self.__mqtt_client.on_connected = self.__on_mqtt_connected
        self.__mqtt_client.on_message = self.__on_mqtt_message
        self.__mqtt_client.start()


    def __on_mqtt_connected(self):
        print("Dom0 MQTT client connected")
        self.__mqtt_client.subscribe(f"{Topics.DELETE_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.SYSTEM_INFO}/request")
        self.__verrou.set()


    def __on_mqtt_message(self, topic:str, payload:dict):
        if topic == f"{Topics.DELETE_FILE}/request":
            self.__handle_delete_file(payload)
        elif topic == f"{Topics.SYSTEM_INFO}/request":
            self.__handle_system_info()


    def __handle_delete_file(self, payload):
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
