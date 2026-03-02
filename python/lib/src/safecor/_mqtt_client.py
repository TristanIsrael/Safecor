""" \author Tristan Israël """

from enum import StrEnum
import json
import threading
import select
import traceback
from typing import Literal, Callable, Optional
try:
    import serial
except ImportError:
    pass
import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
from paho.mqtt.properties import Properties
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode
from . import SysLogger

DEBUG = False
TYPE_CHECKING = True

class ConnectionType(StrEnum):
    ''' @brief Cette énumération permet d'identifier le type de connexion utilisée.
    '''
    UNIX_SOCKET = "unix_socket"
    SERIAL_PORT = "serial_port"
    TCP_DEBUG = "tcp"

class SerialSocket():
    ''' @brief Cette classe implémente une socket série.

    La socket série est utilisée pour communiquer sur un port série dans un DomU
    ou sur une socket de domaine UNIX sur le Dom0.
    '''

    def __init__(self, path:str, baudrate:int):
        self.serial = serial.Serial(port=path, baudrate=baudrate, timeout=1.0, write_timeout=0)
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()


    def recv(self, buffer_size: int) -> bytes:
        #print(f"Wants to read {buffer_size} bytes")
        if self.serial is not None and self.serial.is_open:
            data = self.serial.read(buffer_size)
            #print(f"Read {len(data)} bytes")
            return data

        return b''

    def in_waiting(self) -> int:
        return self.serial.in_waiting

    def pending(self) -> int:
        if self.serial is not None:
            return self.serial.out_waiting
        
        return 0

    def send(self, buffer: bytes) -> int:
        if self.serial is not None and self.serial.is_open:
            #print("send:{}".format(buffer))
            sent = self.serial.write(buffer)
            return sent if sent is not None else 0
        
        return 0

    def close(self) -> None:
        traceback.print_stack()

        if self.serial is not None and self.serial.is_open:
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.serial.close()

    def fileno(self) -> int:
        return self.serial.fileno()

    def setblocking(self, flag: bool) -> None:
        pass


class SerialMQTTClient(mqtt.Client):
    ''' @brief Cette classe permet au client MQTT de communiquer sur un port série.
    '''

    on_connection_lost: Optional[Callable[[], None]] = None

    def __init__(self, path:str, baudrate:int, *args, **kwargs):
        super().__init__(callback_api_version=CallbackAPIVersion.VERSION2, *args, **kwargs)
        self.path = path
        self.baudrate = baudrate
        self._sock = None

    def disconnect(self, reasoncode: ReasonCode | None = None, properties: Properties | None = None):
        self._send_disconnect(reasoncode, properties)
        self.__do_loop()

    def close(self):
        self.disconnect()
        self._sock_close()
        #if self.sock_ is not None:
        #    self.sock_.close()

    def loop_start(self) -> MQTTErrorCode:
        self._thread_terminate = False
        self._thread = threading.Thread(target=self.__do_loop)
        self._thread.daemon = True
        self._thread.start()

        return MQTTErrorCode.MQTT_ERR_SUCCESS

    def __do_loop(self):
        rc = MQTTErrorCode.MQTT_ERR_SUCCESS
        timeout = 1.0

        while not self._thread_terminate:
            if self._sock is None:
                SysLogger("MQTT client").warn("No socket found, exiting loop")
                if self.on_connection_lost is not None:
                    self.on_connection_lost()
                return
            
            # if bytes are pending do not wait in select
            pending_bytes = self._sock.pending()
            if pending_bytes > 0:
                timeout = 0.0

            rlist, _, _ = select.select([self._sock], [], [], timeout)

            if rlist and self._sock.in_waiting() > 0:
                rc = self.loop_read()
                if rc != MQTTErrorCode.MQTT_ERR_SUCCESS:
                    SysLogger("MQTT client").warn(f"Read error {rc}")
                    break

            if self.want_write():
                rc = self.loop_write()
                if rc != MQTTErrorCode.MQTT_ERR_SUCCESS:
                    SysLogger("MQTT client").warn(f"Write error {rc}")
                    break

            rc = self.loop_misc()
            if rc != MQTTErrorCode.MQTT_ERR_SUCCESS:
                SysLogger("MQTT client").warn(f"Misc error {rc}")
                if rc == MQTTErrorCode.MQTT_ERR_CONN_LOST:
                    SysLogger("MQTT client").warn("Connection lost.")
                    if self.on_connection_lost is not None:
                        self.on_connection_lost()

                break

            #time.sleep(0.2)

    def loop_stop(self) -> MQTTErrorCode:
        self._thread_terminate = True

        if self._thread is not None:
            self._thread.join()
            return MQTTErrorCode.MQTT_ERR_SUCCESS

        return MQTTErrorCode.MQTT_ERR_UNKNOWN

    def _create_socket(self):
        try:
            self._sock = SerialSocket(self.path, self.baudrate)
            self._sockpairR = self._sock
            return self._sock
        except Exception as e:
            SysLogger("MQTT client").warn("An error occured while opening the serial port")
            SysLogger("MQTT client").warn(str(e))
            return None

class MqttClient():
    ''' @brief Cette classe permet d'échanger des messages MQTT au sein du système.
    '''

    connection_type:ConnectionType = ConnectionType.UNIX_SOCKET
    connection_string:str = ""
    identifier:str = "unknown"
    on_connected: Optional[Callable[[], None]] = None
    on_message: Optional[Callable[[str, dict], None]] = None
    on_subscribed: Optional[Callable[[], None]] = None
    on_log: Optional[Callable[[int, str], None]] = None
    __message_callbacks = []
    __connected_callbacks = []
    connected = False
    is_starting = False
    __debugging = False

    def __init__(self, identifier:str, connection_type:ConnectionType = ConnectionType.UNIX_SOCKET, connection_string:str = "", debugging = False):
        self.mqtt_client = None
        self.identifier = identifier
        self.connection_type = connection_type
        self.connection_string = connection_string
        self.__debugging = debugging
        self.__subscriptions = []

    def __del__(self):
        self.stop()

    def start(self):
        if self.is_starting or self.connected:
            return
        
        self.is_starting = True
        SysLogger("MQTT client").info(f"Starting MQTT client {self.identifier}")

        if self.connection_type != ConnectionType.SERIAL_PORT:
            self.mqtt_client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=self.identifier,
                transport=self.__get_transport_type(),
                reconnect_on_failure=True
            )
            self.mqtt_client.on_connect = self.__on_connected
            self.mqtt_client.on_message = self.__on_message
            self.mqtt_client.on_subscribe = self.__on_subscribe
            self.mqtt_client.on_disconnect = self.__on_disconnected
            if self.__debugging:
                self.mqtt_client.on_log = self.__on_log

            mqtt_host = "undefined"
            try:
                if self.connection_type == ConnectionType.TCP_DEBUG:
                    mqtt_host = "localhost"
                    self.mqtt_client.connect(host=mqtt_host, keepalive=30)
                elif self.connection_type == ConnectionType.UNIX_SOCKET:
                    mqtt_host = self.connection_string
                    self.mqtt_client.connect(host=mqtt_host, port=1, keepalive=30)
                else:
                    SysLogger("MQTT client").error(f"The connection type {self.connection_type} is not handled")
                    return
            except Exception as e:
                SysLogger("MQTT client").warn(f"Could not connect to the MQTT broker on {mqtt_host}")
                SysLogger("MQTT client").warn(str(e))
                return
            
            self.mqtt_client.loop_start()
        elif self.connection_type == ConnectionType.SERIAL_PORT:
            self.mqtt_client = SerialMQTTClient(
                client_id=self.identifier,
                path=self.connection_string,
                baudrate=115200,
                reconnect_on_failure=True
            )
            self.mqtt_client.on_connect = self.__on_connected
            self.mqtt_client.on_message = self.__on_message
            self.mqtt_client.on_disconnect = self.__on_disconnected
            self.mqtt_client.on_subscribe = self.__on_subscribe
            self.mqtt_client.on_connection_lost = self.__on_connection_lost
            if self.__debugging:
                self.mqtt_client.on_log = self.__on_log

            if DEBUG:
                self.mqtt_client.on_log = self.__on_log
            self.mqtt_client.connect(host="localhost", port=1, keepalive=5)

            self.mqtt_client.loop_start()
        else:
            SysLogger("MQTT client").error(f"The connection type {self.connection_type} is not handled")
            return        

    def add_connected_callback(self, callback):
        self.__connected_callbacks.append(callback)

    def add_message_callback(self, callback):
        self.__message_callbacks.append(callback)

    def del_message_callback(self, callback):
        self.__message_callbacks.remove(callback)

    def reset_message_callbacks(self):
        self.__message_callbacks.clear()

    def stop(self):
        if self.mqtt_client is not None:
            #print("Quit Mqtt client")
            try:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
                if self.connection_type == ConnectionType.SERIAL_PORT:
                    self.mqtt_client.close()
            except:
                #Ignore exceptions when closing
                pass
            finally:
                self.connected = False
                self.is_starting = False

    def subscribe(self, topic:str) -> tuple[MQTTErrorCode, int | None]:
        #print(f"Subscribed to {topic}")
        self.__subscriptions.append(topic)
        return self.mqtt_client.subscribe(topic)

    def unsubscribe(self, topic:str):
        """ Unsubscribes a client from a specific topic """

        #print(f"Unsubscribed from {topic}")
        self.__subscriptions.remove(topic)
        return self.mqtt_client.unsubscribe(topic)

    def unsubscribe_all(self):
        """ Unsubscribes a client from all topics """

        for topic in self.__subscriptions:
            self.unsubscribe(topic)

    def publish(self, topic:str, payload:dict):
        data = json.dumps(payload)
        #print(data)
        #print(len(data))
        self.mqtt_client.publish(topic=topic, payload=data)

    def __get_transport_type(self) -> Literal['tcp', 'unix']:
        if self.connection_type == ConnectionType.TCP_DEBUG:
            return "tcp"
        else:
            return "unix"

    def __on_log(self, client, userdata, level, buf):
        if self.on_log is not None:
            self.on_log(level, buf)

    def __on_message(self, client:mqtt.Client, userdata, msg:mqtt.MQTTMessage):
        #print(f"[{userdata}] Message reçu sur {msg.topic}: {msg.payload.decode()}")        
        try:
            payload = json.loads(msg.payload.decode())
            if self.on_message is not None:
                self.on_message(msg.topic, payload)

            for cb in self.__message_callbacks:
                cb(msg.topic, payload)
        except Exception as e:
            SysLogger("MQTT client").warn("[MQTT Client] Uncaught Exception when handling message:")
            SysLogger("MQTT client").warn(f"Topic : {msg.topic}")
            SysLogger("MQTT client").warn(f"Payload : {msg.payload}")
            SysLogger("MQTT client").warn(f"Exception : {e}")
            SysLogger("MQTT client").warn("** Notice that the error may come from the client callback **")

    def __on_connected(self, client:mqtt.Client, userdata, connect_flags, reason_code, properties):
        SysLogger("MQTT client").info("Connected to the MQTT broker")
        self.connected = True
        self.is_starting = False
        
        if self.on_connected is not None:
            self.on_connected()

        for cb in self.__connected_callbacks:
            cb()

    def __on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        #print("Subscribed to a topic")

        if self.on_subscribed is not None:
            self.on_subscribed(mid)

    def __on_connection_lost(self):
        SysLogger("MQTT client").warn("Connection lost, trying to reconnect.")
        self.is_starting = False
        self.connected = False
        self.start()

    def __on_disconnected(self, *args):
        SysLogger("MQTT client").info("Disconnected from the broker")
        #print("Arguments:")
        #for arg in args:
        #    print(arg)

        #print("Disconnect from the broker")
        #self.mqtt_client.close()
        
    