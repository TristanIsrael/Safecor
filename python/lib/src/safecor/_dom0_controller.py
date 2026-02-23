""" \author Tristan Israël """

import threading
import subprocess
import time
import psutil
from . import Constants, __version__
from . import Logger, FileHelper
from . import ResponseFactory
from . import MqttClient, Topics, MqttHelper, NotificationFactory
from . import System, ComponentState
LIBVIRT_UNAVAILABLE = False
try:
    from . import LibvirtHelper
except ImportError:
    LIBVIRT_UNAVAILABLE = True
    print("Not using libvirt")

class Dom0Controller():
    """ This class handles some of the commands sent by Domains that involve the repository and the system in general 
    (supervision, configuration, etc)    

    The capabilities of the Dom0 controller are:

        - List the files of the repository (:attr:`Topics.LIST_FILES`).
        - Delete a file in the repository (:attr:`Topics.DELETE_FILE`).
        - Calculate a file footprint (:attr:`Topics.FILE_FOOTPRINT`).
        - Shut the system down (:attr:`Topics.SHUTDOWN`).
        - Restart a Domain (:attr:`Topics.RESTART_DOMAIN`). ** The Dom0 cannot be restarted **.
        - Get the system information (:attr:`Topics.SYSTEM_INFO`).
        - Get the energy state (:attr:`Topics.ENERGY_STATE`).
        - Discover the components of the system (:attr:`Topics.DISCOVER_COMPONENTS`).
        - Ping a Domain (:attr:`Topics.PING`).        
        - Notify that the GUI is ready (:attr:`Topics.GUI_READY`).

        All the function can be called using the API or the protocol.

        .. seealso::
            :class:`Api` - The API class

    """    

    __mqtt_lock = threading.Event()
    __is_shutting_down = False

    def __init__(self, mqtt_client: MqttClient):
        """ Instanciates the Dom0 controller.
        
        Args:
            mqtt_client (MqttClient): The instance of the MqttClient class which handles the connexion to the MQTT broker.
        
        """
        self.mqtt_client = mqtt_client

        # Handle Mqtt messages
        self.mqtt_client.on_connected = self.__on_mqtt_connected
        self.mqtt_client.on_message = self.__on_mqtt_message
        
        Logger().setup("System controller", mqtt_client)


    def start(self):
        """ Starts the Dom0 controller.

        When the Dom0 controlelr starts it automatically subscribes to the following topics:

        - :attr:`Topics.LIST_FILES`
        - :attr:`Topics.FILE_FOOTPRINT`
        - :attr:`Topics.SHUTDOWN`
        - :attr:`Topics.RESTART_DOMAIN`
        - :attr:`Topics.GUI_READY`
        - :attr:`Topics.SYSTEM_INFO`
        - :attr:`Topics.ENERGY_STATE`
        - :attr:`Topics.DELETE_FILE`
        - :attr:`Topics.DISCOVER_COMPONENTS`
        - :attr:`Topics.PING`

        After the Dom0 controller is started it is able to answer requests on these topics.
        
        """
        self.mqtt_client.start()
        self.__mqtt_lock.wait()
    

    def __on_mqtt_connected(self):
        Logger().debug("Starting Dom0 controller")
        self.mqtt_client.subscribe(f"{Topics.LIST_FILES}/request")
        self.mqtt_client.subscribe(f"{Topics.FILE_FINGERPRINT}/request")
        self.mqtt_client.subscribe(f"{Topics.SHUTDOWN}/request")
        self.mqtt_client.subscribe(f"{Topics.RESTART_DOMAIN}/request")
        self.mqtt_client.subscribe(Topics.GUI_READY)
        self.mqtt_client.subscribe(f"{Topics.SYSTEM_INFO}/request")
        self.mqtt_client.subscribe(f"{Topics.ENERGY_STATE}/request")
        self.mqtt_client.subscribe(f"{Topics.DELETE_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.DISCOVER_COMPONENTS}/request")
        self.mqtt_client.subscribe(f"{Topics.PING}/request")


    def __on_mqtt_message(self, topic:str, payload:dict):
        # The message will be handled in a thread        
        threading.Thread(target=self.__message_worker, args=(topic, payload, )).start()


    def __message_worker(self, topic:str, payload:dict):
        """ Cette fonction traite uniquement les messages destinés au Dom0 """
        
        try:
            if topic == f"{Topics.LIST_FILES}/request":
                self.__handle_list_files(payload)
            elif topic == f"{Topics.FILE_FINGERPRINT}/request":
                self.__handle_file_fingerprint(payload)
            elif topic == f"{Topics.SHUTDOWN}/request":
                self.__handle_shutdown(payload)
            elif topic == f"{Topics.RESTART_DOMAIN}/request":
                self.__handle_restart_domain(payload)
            elif topic == Topics.GUI_READY:
                self.__handle_gui_ready(payload)
            elif topic == f"{Topics.ENERGY_STATE}/request":
                self.__handle_energy_state()
            elif topic == f"{Topics.SYSTEM_INFO}/request":
                self.__handle_system_info()
            elif topic == f"{Topics.DELETE_FILE}/request":
                self.__handle_delete_file(payload)
            elif topic == f"{Topics.DISCOVER_COMPONENTS}/request":
                self.__handle_discover_components()
            elif topic == f"{Topics.PING}/request":
                self.__handle_ping(payload)
        except Exception:
            Logger.print("An exception occured while handling the message")



    def __handle_list_files(self, payload:dict) -> None:
        if not self.__is_storage_request(payload):
            return 

        # Récupère la liste des fichiers                    
        fichiers = FileHelper.get_files_list(Constants.STR_REPOSITORY, True)

        # Génère la réponse
        response = ResponseFactory.create_response_list_files(Constants.STR_REPOSITORY, fichiers)
        self.mqtt_client.publish(f"{Topics.LIST_FILES}/response", response)


    def __handle_file_fingerprint(self, payload:dict) -> None:
        if not self.__is_storage_request(payload):
            return
                    
        filepath = payload.get("filepath")
        disk = payload.get("disk")

        if filepath is None or disk is None:
            # S'il manque un argument on envoie une erreur
            Logger().error("La commande est incomplète : il manque le nom du disque et/ou le chemin du fichier")
            return
        
        # Calcule l'empreinte
        repository_path = Constants.DOM0_REPOSITORY_PATH
        fingerprint = FileHelper.calculate_fingerprint(f"{repository_path}/{filepath}")

        Logger().info(f"Fingerprint = {fingerprint}")
        
        # Génère la réponse
        response = ResponseFactory.create_response_file_fingerprint(filepath, disk, fingerprint)
        self.mqtt_client.publish(f"{Topics.FILE_FINGERPRINT}/response", response)


    def __handle_shutdown(self, payload:dict):
        if self.__is_shutting_down:
            return
        
        Logger().warn("System shutdown requested!")
        self.__is_shutting_down = True

        # There is currently no rule for the shutdown, so we accept it
        response = ResponseFactory.create_response_shutdown(True)
        self.mqtt_client.publish(f"{Topics.SHUTDOWN}/response", response)

        # We wait 5 seconds to let the GUIs and clients acknowledge the information
        time.sleep(5)

        # Then we shut the system down
        cmd = ["poweroff"]
        subprocess.run(cmd)


    def __handle_restart_domain(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["domain_name"]):
            Logger().error(f"Missing argument domain_name in the topic {Topics.RESTART_DOMAIN}")
            return
        
        domain_name = payload.get("domain_name", "")
        self.__reboot_domain(domain_name)


    def __handle_gui_ready(self, payload:dict):
        # When GUI is ready we hide the splash screen
        cmd = ["killall", "feh"]
        subprocess.run(cmd)


    def __is_storage_request(self, payload:dict) -> bool:
        if payload.get("disk") is not None:
            return payload.get("disk") == Constants.STR_REPOSITORY
        else:
            return False


    def __reboot_domain(self, domain_name:str):
        if LIBVIRT_UNAVAILABLE:
            print("Libvirt is unavailable. Cannot reboot domain")
            return
        
        if LibvirtHelper.reboot_domain(domain_name):
            Logger().info(f"Rebooting domain {domain_name}")
            response = ResponseFactory.create_response_restart_domain(domain_name, True)
            self.mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/response", response)
        else:
            Logger().error(f"The domain {domain_name} won't reboot")
            response = ResponseFactory.create_response_restart_domain(domain_name, False)
            self.mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/response", response)

        #cmd = ["xl", "reboot", domain_name]
        #res = subprocess.run(cmd)

        #if res.returncode == 0:
        #    Logger().info(f"Rebooting domain {domain_name}")
        #    response = ResponseFactory.create_response_restart_domain(domain_name, True)
        #    self.mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/response", response)
        #else:
        #    Logger().error(f"The domain {domain_name} won't reboot")
        #    response = ResponseFactory.create_response_restart_domain(domain_name, False)
        #    self.mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/response", response)


    def __handle_energy_state(self):
        battery = psutil.sensors_battery()

        if battery:
            payload = NotificationFactory.create_notification_energy_state(battery)
            self.mqtt_client.publish(f"{Topics.ENERGY_STATE}/response", payload)


    def __handle_system_info(self):
        payload = System.get_system_information()
 
        self.mqtt_client.publish(f"{Topics.SYSTEM_INFO}/response", payload)

    def __handle_delete_file(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            Logger().error(f"The command {Topics.DELETE_FILE} misses argument(s)", "Dom0")
            return

        disk = payload["disk"]

        if disk != Constants.STR_REPOSITORY:
            # This file is not stored in the repository so we ignore it
            return

        filepath = payload["filepath"]
        repository_path = Constants.DOM0_REPOSITORY_PATH
        storage_filepath = f"{repository_path}/{filepath}"

        if not FileHelper().remove_file(storage_filepath):
            Logger().error(f"Removal of file {filepath} from repository failed")
        else:
            Logger().info(f"Removed file {filepath} from repository")
        
    def __handle_discover_components(self):
        comp = ResponseFactory.create_entry_component_state(Constants.SAFECOR_SYSTEM_CONTROLLER,
            "Core controller",
            "Dom0",
            ComponentState.READY
        )

        payload = ResponseFactory.create_response_component_state([comp])

        self.mqtt_client.publish(f"{Topics.DISCOVER_COMPONENTS}/response", payload)

    def __handle_ping(self, payload):
        ping_id = payload.get("id", "")
        data = payload.get("data", "")
        sent_at = payload.get("sent_at", "")
        payload = ResponseFactory.create_response_ping(ping_id, "Dom0", data, sent_at)

        self.mqtt_client.publish(f"{Topics.PING}/response", payload)

    