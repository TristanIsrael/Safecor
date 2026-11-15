"""MQTT client module

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import json
from enum import StrEnum
from typing import Callable, Literal, Optional

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode

from . import SysLogger

DEBUG = False
TYPE_CHECKING = True


class ConnectionType(StrEnum):
    """@brief This enumeration identifies the type of connection used.

    UNIX_SOCKET: the broker is reached through a UNIX domain socket.
    TCP_DEBUG: the broker is reached over TCP on localhost (development only).
    """

    UNIX_SOCKET = "unix_socket"
    TCP_DEBUG = "tcp"


class MqttClient:
    """This class is used to exchange MQTT messages within the system.

    Class attributes:

    - ``connection_type`` (ConnectionType): the type of the connection to the broker.
    - ``connection_string`` (str): the connection string (the UNIX socket path, the
      serial port path, or the TCP host depending on the connection type).
    - ``identifier`` (str): the client identifier (used as the MQTT client ID).
    - ``on_connected``: callback invoked when the client (re)connects to the broker.
    - ``on_message``: callback invoked for every message received on a subscribed
      topic.
    - ``on_subscribed``: callback invoked when the broker acknowledges a
      subscription.
    - ``on_log``: callback invoked with the paho log messages (debugging only).
    - ``connected`` (bool): True while the client is connected to the broker.
    - ``is_starting`` (bool): True while the client is trying to connect.
    """

    connection_type: ConnectionType = ConnectionType.UNIX_SOCKET
    connection_string: str = ""
    identifier: str = "unknown"
    on_connected: Optional[Callable[[], None]] = None
    on_message: Optional[Callable[[str, dict], None]] = None
    on_subscribed: Optional[Callable[[], None]] = None
    on_log: Optional[Callable[[int, str], None]] = None
    __message_callbacks = []
    __connected_callbacks = []
    connected = False
    is_starting = False
    __debugging = False

    def __init__(
        self,
        identifier: str,
        connection_type: ConnectionType = ConnectionType.UNIX_SOCKET,
        connection_string: str = "",
        debugging=False,
    ):
        """Creates a MQTT client.

        Args:
            identifier(str): The client identifier (used as the MQTT client ID).
            connection_type(ConnectionType): The type of the connection to the broker.
            connection_string(str): The connection string (the UNIX socket path, the
                serial port path, or the TCP host depending on the connection type).
            debugging(bool): If True, the paho log messages are forwarded to on_log.
        """
        self.mqtt_client = None
        self.identifier = identifier
        self.connection_type = connection_type
        self.connection_string = connection_string
        self.__debugging = debugging
        self.__subscriptions = []

    def __del__(self):
        self.stop()

    def start(self):
        """Creates the underlying paho client and connects it to the broker.

        The transport is selected by the connection type: a UNIX domain
        socket or TCP on localhost (debugging).
        No-op if the client is already connected or starting.
        """
        if self.is_starting or self.connected:
            return

        self.is_starting = True
        SysLogger("MQTT-client").info(f"Starting MQTT client {self.identifier}")

        self.mqtt_client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.identifier,
            transport=self.__get_transport_type(),
            reconnect_on_failure=True,
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
                SysLogger("MQTT-client").error(
                    f"The connection type {self.connection_type} is not handled"
                )
                return
        except Exception as e:
            SysLogger("MQTT-client").warn(
                f"Could not connect to the MQTT broker on {mqtt_host}"
            )
            SysLogger("MQTT-client").warn(str(e))
            return

        self.mqtt_client.loop_start()

    def add_connected_callback(self, callback):
        """Registers a callback invoked every time the client (re)connects to the broker.

        Args:
            callback: A callable with no argument.
        """
        self.__connected_callbacks.append(callback)

    def add_message_callback(self, callback):
        """Registers a callback invoked for every received message.

        Args:
            callback: A callable invoked with the topic (str) and the payload (dict).
        """
        self.__message_callbacks.append(callback)

    def del_message_callback(self, callback):
        """Removes a previously registered message callback.

        Args:
            callback: The callback to remove.
        """
        self.__message_callbacks.remove(callback)

    def reset_message_callbacks(self):
        """Removes all the registered message callbacks."""
        self.__message_callbacks.clear()

    def stop(self):
        """Disconnects from the broker and stops the network loop.

        Exceptions raised while closing the client are ignored.
        """
        if self.mqtt_client is not None:
            # print("Quit Mqtt client")
            try:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
            except Exception:
                # Ignore exceptions when closing
                pass
            finally:
                self.connected = False
                self.is_starting = False

    def subscribe(self, topic: str) -> tuple[MQTTErrorCode, int | None]:
        """Subscribes to a topic on the broker. The topic is tracked by the client.

        Args:
            topic(str): The topic to subscribe to.

        Returns:
            tuple[MQTTErrorCode, int | None]: The paho result code and the message ID.
        """
        # print(f"Subscribed to {topic}")
        self.__subscriptions.append(topic)
        return self.mqtt_client.subscribe(topic)

    def unsubscribe(self, topic: str):
        """Unsubscribes a client from a specific topic"""

        # print(f"Unsubscribed to {topic}")
        self.__subscriptions.remove(topic)
        return self.mqtt_client.unsubscribe(topic)

    def unsubscribe_all(self):
        """Unsubscribes a client from all topics"""

        for topic in self.__subscriptions:
            self.unsubscribe(topic)

    def publish(self, topic: str, payload: dict):
        """Publishes a payload on a topic. The payload is serialized as JSON.

        Args:
            topic(str): The topic to publish to.
            payload(dict): The payload to publish.
        """
        data = json.dumps(payload, ensure_ascii=True)
        # print(data)
        # print(len(data))
        self.mqtt_client.publish(topic=topic, payload=data)

    def __get_transport_type(self) -> Literal["tcp", "unix"]:
        if self.connection_type == ConnectionType.TCP_DEBUG:
            return "tcp"
        else:
            return "unix"

    def __on_log(self, client, userdata, level, buf):
        if self.on_log is not None:
            self.on_log(level, buf)

    def __on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if self.on_message is not None:
                self.on_message(msg.topic, payload)

            for cb in self.__message_callbacks:
                cb(msg.topic, payload)
        except Exception as e:
            SysLogger("MQTT-client").warn(
                "[MQTT Client] Uncaught Exception when handling message:"
            )
            SysLogger("MQTT-client").warn(f"Topic : {msg.topic}")
            SysLogger("MQTT-client").warn(f"Payload : {msg.payload}")
            SysLogger("MQTT-client").warn(f"Exception : {e}")
            SysLogger("MQTT-client").warn(
                "** Notice that the error may come from the client callback **"
            )

    def __on_connected(
        self, client: mqtt.Client, userdata, connect_flags, reason_code, properties
    ):
        SysLogger("MQTT-client").info("Connected to the MQTT broker")
        self.connected = True
        self.is_starting = False

        # Every (re)connection starts a clean session, so the broker has
        # forgotten the previous subscriptions. Re-apply the tracked
        # topics (deduplicated) before notifying the callers: on a first
        # connection the list is empty and this is a no-op.
        for topic in dict.fromkeys(self.__subscriptions):
            self.mqtt_client.subscribe(topic)

        if self.on_connected is not None:
            self.on_connected()

        for cb in self.__connected_callbacks:
            cb()

    def __on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        # print("Subscribed to a topic")

        if self.on_subscribed is not None:
            self.on_subscribed(mid)

    def __on_connection_lost(self):
        SysLogger("MQTT-client").warn("Connection lost, trying to reconnect.")
        self.is_starting = False
        self.connected = False
        self.start()

    def __on_disconnected(self, *args):
        SysLogger("MQTT-client").info("Disconnected from the broker")
        # print("Arguments:")
        # for arg in args:
        #    print(arg)

        # print("Disconnect from the broker")
        # self.mqtt_client.close()
