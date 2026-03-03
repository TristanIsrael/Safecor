""" \author Tristan Israël """

from paho.mqtt.enums import MQTTErrorCode
import tempfile
import os
import zlib
import base64
import atexit
import signal
from datetime import datetime

from . import RequestFactory, Topics, NotificationFactory, ResponseFactory, DiskState
from . import Logger, MqttClient, System, SingletonMeta, MqttFactory, Constants

class Api(metaclass=SingletonMeta):
    """     
    This class allows a third-party program to send commands or receive notifications without having to use the socket directly.

    The API provides a simple set of functions for sending commands and receiving notifications. However, it does not handle the formatting of commands, 
    which is managed by the :class:`RequestFactory`, :class:`ResponseFactory`, :class:`NotificationFactory` or :class:`ApiHelper` classes.

    The API can only be used within a user Domain (DomU).

    To use the API, simply instantiate the Api class and open the socket by calling the :func:`start()` function. Then, the other functions allow 
    sending and receiving messages and notifications.

    .. seealso::
        :class:`ApiHelper` - The API helper class

    Singleton
    =========

    This class is a singleton because it keeps information about the context. There is only one instance in an application.

    Example of usage :

    ::

        Api().add_ready_callback(self.__on_ready)
        Api().start()        

    Asynchronous
    ============

    All commands operate asynchronously. The result of executing a command will only be communicated through a notification or a response. 
    Therefore, a callback function must be provided to the API in order to receive responses. The internal topics
    provided in the :class:`Topics` use the suffix ``/request`` and ``/response`` to differenciate the query and the answer. 
    When an answer is expected on a topic, it will always be suffixed with ``/response``.

    **The callbacks are**:

    - :func:`Api.add_message_callback` - A message has been received
    - :func:`Api.add_ready_callback` - The API is ready    
    - :func:`Api.add_restart_callback` - The restart has been accepted or refused by the core
    - :func:`Api.add_shutdown_callback` - The shutdown has been accepted or refused by the core
    - :func:`Api.add_subscription_callback` - The broker acknowledged a subscription

    Subscription
    ============

    **The messages and notifications can be received only when the following conditions are met:**

    - The topic has been subscribed (see :func:`Api.subscribe`)
    - A message callback function has been provided (see :func:`Api.add_message_callback`)

    How to use the API
    ==================
    
    The sequence to correctly handle the connection and subscriptions on a broker is the following:

        1. start
        2. on ready
            - subscribe
        3. on subscribed
            - continue the app

    Here is an example:

    ::

        from safecor import MqttFactory, Api
                
        subscriptions = [ "my-topic-1", "my-topic-2" ]

        def start():
            Api().start(domain_identifier="my-domain")
            Api().add_ready_callback(on_connected)

        def on_connected():
            Api().add_subscription_callback(on_subscribed)
            Api().add_message_callback(self.on_message_received)
            success, mid = Api().subscribe(<topic name>)
            if success:
                subscriptions.append(mid)

        def on_subscribed(mid):
            if mid in subscriptions:
                <continue app starting>

        if __name__ == "__main__":
            start()

    """

    __ready_callbacks = []
    __message_callbacks = []
    __subscriptions = []
    __shutdown_callbacks = []
    __restart_callbacks = []
    __subscription_callbacks = []
    __recording = False
    __mqtt_client = None
    __ping_id = 0
    __logfile = "/var/log/safecor.log"


    def start(self, mqtt_client:MqttClient = None, domain_identifier:str = "undefined", recording:bool = False, logfile:str = Constants.LOCAL_LOG_FILEPATH):
        """
        Starts the API by connecting to the MQTT broker and opening a log file if asked.

        When no mqtt_client argument is provided the API tries to create a DomU client with the identifier provided.

        Args:
            mqtt_client (MqttClient): The instance of the MqttClient class which handles the connexion to the MQTT broker.
            domain_identifier (str): The unique identifier (label) for the domain connection.
            recording (bool): If true, the events will be recorded in a log file.
            logfile (str): If recording is true, the location of the log file can provided with this parameter.
        """
        if mqtt_client is None:
            self.__mqtt_client = MqttFactory.create_mqtt_client_domu(domain_identifier)
        else:
            self.__mqtt_client = mqtt_client

        self.__recording = recording
        self.__logfile = logfile

        self.__mqtt_client.on_connected = self.__on_mqtt_connected
        self.__mqtt_client.on_message = self.__on_message_received
        self.__mqtt_client.on_subscribed = self.__on_subscribed
        self.__mqtt_client.on_log = self.__on_log

        self.__mqtt_client.start()


    def stop(self):
        """
        Stops the Api by disconnecting from the MQTT broker.        
        """
        if self.__mqtt_client is not None:
            self.__mqtt_client.stop()


    def get_mqtt_client(self):
        """
        Returns the current MQTT client instance.
        """
        return self.__mqtt_client


    def add_message_callback(self, callback_fn):
        """
        Adds a callback for receiving messages

        The callback will receive the following arguments:

        - topic:str The topic of the message
        - payload:dict The payload as a JSON object

        Args:
            callback_fn(Callable): A function which will be called by the API when a message arrives.
        """
        if callback_fn is not None:
            if callback_fn not in self.__message_callbacks:
                self.__message_callbacks.append(callback_fn)
        else:
            print("WARNING: message callback function is None")


    def add_ready_callback(self, callback_fn):
        """
        Adds a callback to notify when the API is connected to the MQTT broker and ready.

        The callback won't receive any argument

        Args:
            callback_fn(Callable): A function which will be called by the API when it is connected to the MQTT broker.
        """
        if callback_fn is not None:
            if callback_fn not in self.__ready_callbacks:
                self.__ready_callbacks.append(callback_fn)
        else:
            print("WARNING: ready callback function is None")

    def add_subscription_callback(self, callback_fn):
        """
        Adds a callback to notify when a subscription has been acknowledged by the broker.

        The callback will receive the following arguments:

        - topic:str The topic subscribed

        Args:
            callback_fn(Callable): A function which will be called by the API when the subscription has been acknowledged.
        """
        if callback_fn is not None:
            if callback_fn not in self.__subscription_callbacks:
                self.__subscription_callbacks.append(callback_fn)

    def add_shutdown_callback(self, callback_fn):
        """
        Adds a callback to notify when the system has started shutting down.

        Args:
            callback_fn(Callable): A function which will be called by the API when the system is shutting down.
        """
        if callback_fn is not None:
            if callback_fn not in self.__shutdown_callbacks:
                self.__shutdown_callbacks.append(callback_fn)
        else:
            print("WARNING: shutdown callback function is None")


    def add_restart_callback(self, callback_fn):
        """
        Adds a callback to notify when the system is restarting a component.

        Args:
            callback_fn(Callable): A function which will be called by the API when the system is restarting a component.
        """
        if callback_fn is not None:
            if callback_fn not in self.__restart_callbacks:
                self.__restart_callbacks.append(callback_fn)
        else:
            print("WARNING: shutdown callback function is None")


    def subscribe(self, topic:str) -> tuple[bool, int | None]:
        """
        Subscribes to a topic on the broker.

        If the function subscribed to is a Safecor function, the :class:`Topics` class provides the reference of the topic names.                

        Args:
            topic(str): The topic to subscribe to.

        Returns:
            tuple[bool, int | None]: A tuple containing the result as bool and the ID of the subscription
        """
        if not topic in self.__subscriptions:
            error_code, mid = self.__mqtt_client.subscribe(topic)
            if error_code != MQTTErrorCode.MQTT_ERR_SUCCESS:
                print(f"WARNING: An error occured while subscribing to the topic {topic}")
                print(error_code)
                return (False, None)
            else:
                return (True, mid)


    def publish(self, topic:str, payload:dict):
        """
        Publish a message on the MQTT broker.

        The message is formatted in `JSON` and can provided directly as a `dict`.

        Args:
            topic(str): The topic to publish to.
            payload(dict): The message formatted in `JSON`.
        """
        self.__mqtt_client.publish(topic, payload)


    ####
    # Fonctions de journalisation
    #
    def debug(self, message : str, module: str = ""):
        """
        Publish a `debug` message.

        Args:
            message(str): The message to publish
            module(str, optional): The name of the component involved.
        """
        Logger().debug(message, module)


    def info(self, message : str, module: str = ""):
        """
        Publish a `info` message.

        Args:
            message(str): The message to publish
            module(str, optional): The name of the component involved.
        """
        Logger().info(message, module)


    def warn(self, message : str, module: str = ""):
        """
        Publish a `warn` message.

        Args:
            message(str): The message to publish
            module(str, optional): The name of the component involved.
        """
        Logger().warn(message, module)


    def error(self, message : str, module: str = ""):
        """
        Publish an `error` message.

        Args:
            message(str): The message to publish
            module(str, optional): The name of the component involved.
        """
        Logger().error(message, module)


    def critical(self, message : str, module: str = ""):
        """
        Publish a `critical` message.

        Args:
            message(str): The message to publish
            module(str, optional): The name of the component involved.
        """
        Logger().critical(message, module)


    ####
    # Fonctions de gestion des supports de stockage
    #
    def get_disks_list(self):
        """
        Asks the system to provide the list of external disks connected.

        The response is provided on the topic :attr:`Topic.LIST_DISKS`.
        """
        self.__mqtt_client.publish(f"{Topics.LIST_DISKS}/request", {})


    def get_files_list(self, disk: str, recursive:bool = False, from_dir:str = ""):
        """
        Asks the system to provide the list of files of an external disk or the repository.

        The response is provided on the topic :attr:`Topics.LIST_FILES`

        By default the listing is done from the root of the disk. This can be changed by setting the 
        argument `from_dir` to a specifi directory of the disk.

        By default the listing is not recursive, which means that the system will only look in the
        directory provided and not in the subdirectories if any. This can be changed by setting the
        argument `from_dir`.

        **Performance consideration**

        If the disk has a large number of files and nestes folders, the recursive listing will take a
        long time and return a single response with a large JSON string. **This should be avoided for
        performance reasons**. 

        Always prefer a pure asynchronous method of listing all the files and directories by listing
        the files only *not recursively* and send new queries for the remaining directories.

        Thus, the system will always be very efficient and responsive instead of waiting for a big 
        result to be provided.

        Please also consider using a **lazy-loading** strategy which minimizes the load on the system
        by avoiding the listing of files which are not necessary and delays the listing when it is
        necessary.

        The response is provided on the topic :attr:`Topic.LIST_FILES`.

        Args:
            disk(str): The name of the disk.
            recursive(bool): Looks for files recursively if True.
            from_dir(str, optional): The starting directory for the listing.
        """
        payload = RequestFactory.create_request_files_list(disk, recursive, from_dir)
        self.__mqtt_client.publish(f"{Topics.LIST_FILES}/request", payload)


    def read_file(self, disk:str, filepath:str):
        """
        Copies a file into the *repository*.

        When the file is created the :attr:`Topic.NEW_FILE` notification is sent.

        Args:
            disk(str): The source disk.
            filepath(str): The full path of the file to be copied.
        """
        payload = RequestFactory.create_request_read_file(disk, filepath)
        self.__mqtt_client.publish(f"{Topics.READ_FILE}/request", payload)


    def copy_file(self, source_disk:str, filepath:str, destination_disk:str):
        """
        Copies a file from a disk to another.

        When the file is created the :attr:`Topic.NEW_FILE` notification is sent.

        Args:
            source_disk(str): The source disk.
            filepath(str): The full path of the file to be copied.
            destination_disk(str): The destination disk.
        """
        payload = RequestFactory.create_request_copy_file(source_disk, filepath, destination_disk)
        self.__mqtt_client.publish(f"{Topics.COPY_FILE}/request", payload)


    def delete_file(self, filepath:str, disk:str):
        """
        Removes a file from a disk (including the storage).

        When the storage is involved, please use the :attr:`Constantes.REPOSITORY`.

        In case of an error, the :attr:`Topic.ERROR` notification is sent.
        """
        payload = RequestFactory.create_request_delete_file(filepath, disk)
        self.__mqtt_client.publish(f"{Topics.DELETE_FILE}/request", payload)


    def get_file_fingerprint(self, filepath:str, disk:str):
        """
        Compute the fingerprint of a file.

        The response is provided on the topic :attr:`Topic.FILE_FINGERPRINT`.

        Args:
            filepath(str): The full path of the file.
            disk(str): The disk on which the file is located.
        """
        payload = RequestFactory.create_request_get_file_fingerprint(filepath, disk)
        self.__mqtt_client.publish(f"{Topics.FILE_FINGERPRINT}/request", payload)


    def create_file(self, filepath:str, disk:str, contents:bytes, binary=False):
        """
        Creates a new file on a disk by providing raw data.

        The directories will be created if necessary before creating the file on the disk.        

        **Binary/string data**

        Both binary and string data can be provided but when providing binary data, they will
        be encoded in Base64 before being sent to the broker because only text messages can
        be exchanged in MQTT. If binary data are provided, the argument `binary` **must** be 
        set to `True`.

        When the file has been created, the notification :attr:`Topic.NEW_FILE` is sent.

        Args:
            filepath(str): The full path of the file.
            disk(str): The disk on which the file will be created.
            contents(bytes): The data to write in the file.
            binary(bool, optional): If True, it means that the data provided are binary.
        """

        data = contents if not binary else zlib.compress(contents, level=1)
        payload = RequestFactory.create_request_create_file(filepath, disk, base64.b64encode(data), binary)
        self.__mqtt_client.publish(f"{Topics.CREATE_FILE}/request", payload)


    def mount_file(self, disk:str, filepath:str):
        """
        Tries to mount a virtual disk (ISO, VMDK, etc).

        If the mount succeeded, a disk state notification will be sent.

        Args:
            disk(str): The disk on which the file is located.
            filepath(str): The path of the file to mount.
        """

        payload = RequestFactory.create_request_mount_file(disk, filepath)
        self.__mqtt_client.publish(f"{Topics.MOUNT_FILE}/request", payload)
    
    def archive_extensions_handled(self):
        """ Returns the list of file extensions handled by the mount function """

        return Constants.ARCHIVE_EXTENSIONS_HANDLED


    def unmount(self, disk:str):
        """
        Unmounts a disk that has been previously mounted

        If the unmount succeeded, a disk state notification will be sent.

        Args:
            disk(str): The disk name.
        """

        payload = RequestFactory.create_request_unmount(disk)
        self.__mqtt_client.publish(f"{Topics.UNMOUNT}/request", payload)


    def discover_components(self) -> None:
        """
        Asks all the components of the system to notify their information and state.

        The response is provided on the topic :attr:`Topic.DISCOVER_COMPONENTS`
        """
        self.__mqtt_client.publish(f"{Topics.DISCOVER_COMPONENTS}/request", {})


    def publish_components(self, components:list) -> None:
        """
        Publishes a list of components and their state.

        The payload should be created using the fonction :func:`ResponseFactory.create_response_component_state`.
        
        The format of a component state structure is the following::

            {
                "id": "unique identifier of the component,
                "domain_name": "automatically provided by Safecor using the hostname",
                "label": "The name of the component",
                "type": "a key identifying the type or category of the component",
                "state": "The current state of the component. See EtatComposant",
                "version": "The software version of the component",
                "description": "A paragraph describing the component"
            }

        Args:
            components(list): a List of components in the form of dictionaries.
        """
        payload = {
            "components": components
        }
        self.__mqtt_client.publish(f"{Topics.DISCOVER_COMPONENTS}/response", payload)


    def request_energy_state(self) -> None:
        """
        Asks the system the state of the power supply.

        The response is provided on the topic :attr:`Topic.ENERGY_STATE`
        """
        self.__mqtt_client.publish(f"{Topics.ENERGY_STATE}/request", {})


    def request_system_info(self) -> None:
        """
        Asks the system to provide technical information.

        Here is an example of the result provided::

            {
                "core": {
                    "version": "1.1", 
                    "debug_on": false
                }, 
                "system": {
                    "os": {
                        "name": "Linux", 
                        "release": "6.12.20-0-lts", 
                        "version": "#1-Alpine SMP PREEMPT_DYNAMIC 2025-03-24 08:09:11"
                    }, 
                    "machine": {
                        "arch": "x86_64", 
                        "processor": "", 
                        "platform": "Linux-6.12.20-0-lts-x86_64-with", 
                        "cpu": {
                            "count": 12, 
                            "freq_current": 1689.5970000000004, 
                            "freq_min": 0.0, 
                            "freq_max": 0.0, 
                            "percent": 0.0
                        }, 
                        "memory": {
                            "total": 405987328, 
                            "available": 103829504, 
                            "percent": 74.4, 
                            "used": 252207104, 
                            "free": 20271104
                        }, 
                        "load": {
                            "1": 0.4306640625, 
                            "5": 0.16650390625, 
                            "15": 0.0595703125
                        }
                    }, 
                    "boot_time": 1747205332.0, 
                    "uuid": "11ec0800-4fb9-11ef-bd38-ad993f2e7700",
                    "storage": {
                        "total": 12345678,
                        "used": 0,
                        "free": 12345678,
                        "files": 0
                    }
                }
            }        

        The response is provided on the topic :attr:`Topic.SYSTEM_INFO`
        """

        self.__mqtt_client.publish(f"{Topics.SYSTEM_INFO}/request", {})


    def clear_sys_usb_queues(self):
        """ Queries sys-usb to clear its queues.
        """

        Api().publish(f"{Topics.SYS_USB_CLEAR_QUEUES}/request", {})


    ####
    # Fonctions de notification
    #
    def notify_disk_added(self, disk):
        """
        Sends a notification to inform the other components an external storage has been added to the system.

        **This notification is for internal use only**
        """
        payload = NotificationFactory.create_notification_disk_state(disk, DiskState.CONNECTED.value)
        self.__mqtt_client.publish(Topics.DISK_STATE, payload)
    

    def notify_disk_removed(self, disk):
        """
        Sends a notification to inform the other components an external storage has been removed from the system.

        **This notification is for internal use only**
        """
        payload = NotificationFactory.create_notification_disk_state(disk, DiskState.DISCONNECTED.value)
        self.__mqtt_client.publish(Topics.DISK_STATE, payload)


    def notify_gui_ready(self) -> None:
        """
        Sends a notification to inform the other components the Graphical User Interface is ready.

        **This notification is mandatory to make the splash screen disappear when the GUI is ready, otherwise
        the GUI of the system would remain behind the splash screen**
        """
        self.__mqtt_client.publish(Topics.GUI_READY, {})


    ####
    # Workflow functions
    #
    def shutdown(self):
        """
        Makes the system shutdown.

        When a shutdown is asked by a Domain, typically the GUI, a notification is
        sent to all the components to inform them of the shutdown so they can get
        prepared.

        The response is sent on the topic :attr:`Topics.SHUTDOWN` with the following payload::

            {
                "state": "accepted or refused"
                "reason": "the reason why the shutdown was refused"
            }
        """       
        self.__mqtt_client.publish(f"{Topics.SHUTDOWN}/request", {})


    def restart_domain(self, domain_name:str):
        """
        Makes a Domain restart.

        The response is sent on the topic :attr:`Topics.RESTART_DOMAIN` with the following payload::

            {
                "domain_name": "The Domain name",
                "state": "accepted or refused",
                "reason": "The reason why the restart was refused"
            }

        Args:
            domain_name(str): The name of the Domain to restart.
        """
        payload = RequestFactory.create_request_restart_domain(domain_name)
        self.__mqtt_client.publish(f"{Topics.RESTART_DOMAIN}/request", payload)


    ####
    # Debugging functions
    #
    def ping(self, target_domain:str, data:str = ""):
        """
        Sends a ping request to a specific user Domain

        The ping request is peer-to-peer, so the topic format is a little different from
        other topics. The name of the target is in the topic so it can be routed by
        the broker.

        The request should be constructed with :func:`RequestFactory.create_request_ping`.

        Args:
            target_domain(str): The name of the targetted Domain.
            data(str, optional): Data to be sent to the target.
        """
        
        self.__ping_id += 1
        payload = RequestFactory.create_request_ping(self.__ping_id, System.domain_name(), data, datetime.now().timestamp()*1000)
        self.__mqtt_client.publish(f"{Topics.PING}/{target_domain}/request", payload)

    ####
    # Private functions
    #    
    def __on_mqtt_connected(self):
        Logger().setup("Api", mqtt_client=self.__mqtt_client, recording=self.__recording, filename=self.__logfile)

        # Automatically subscribe to some topics
        self.subscribe(f"{Topics.PING}/{System.domain_name()}/request")
        self.subscribe(f"{Topics.SHUTDOWN}/response")
        self.subscribe(f"{Topics.RESTART_DOMAIN}/response")
        
        for cb in self.__ready_callbacks:
            cb()


    def __on_message_received(self, topic:str, payload:dict):
        # Intercept shutdown response
        if topic == f"{Topics.SHUTDOWN}/response":
            self.__on_shutdown(payload)
            return # Stop here
        
        # Intercept restart domain response
        if topic == f"{Topics.RESTART_DOMAIN}/response":
            self.__on_restart_domain(payload)
            return # Stop here
        
        # Intercept ping request
        if topic == f"{Topics.PING}/{System.domain_name()}/request":
            self.__on_ping(payload)
            return # Stop here

        for cb in self.__message_callbacks:
            try:
                cb(topic, payload)
            except Exception:
                Logger.print("An exception has been raised by the callback")                


    def __on_shutdown(self, payload:dict):
        success = payload.get("state", "") == "accepted"
        reason = payload.get("reason", "")

        for cb in self.__shutdown_callbacks:
            cb(success, reason)


    def __on_subscribed(self, mid):
        try:
            for cb in self.__subscription_callbacks:
                if cb is not None:
                    cb(mid)
        except Exception as e:
            print(f"WARNING: an exception occured in the callback on_subscribe {cb}")
            print(str(e))

    def __on_log(self, level, buf):
        print(f"MQTT event: level={level}, message={buf}")

    def __on_restart_domain(self, payload:dict):
        success = payload.get("state", "") == "accepted"
        domain_name = payload.get("domain_name", "")
        reason = payload.get("reason", "")

        for cb in self.__restart_callbacks:
            cb(domain_name, success, reason)

    def __on_ping(self, payload: dict):        
        payload = ResponseFactory.create_response_ping(payload.get("id", ""), System.domain_name(), payload.get("data", ""), payload.get("sent_at", ""))
        source = payload.get("source", "")
        self.__mqtt_client.publish(f"{Topics.PING}/{source}/response", payload)

def cleanup(*args, **kwargs):
    Api().stop()

atexit.register(cleanup)
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
