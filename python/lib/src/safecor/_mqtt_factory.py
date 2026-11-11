"""  Mqtt Factory

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from . import MqttClient, ConnectionType, Constants

class MqttFactory():

    @staticmethod
    def create_mqtt_client_domu(identifier:str) -> MqttClient:
        return MqttClient(identifier, ConnectionType.SERIAL_PORT, Constants.SERIAL_PORT_MSG)
    
    @staticmethod
    def create_mqtt_client_dom0(identifier:str) -> MqttClient:
        return MqttClient(identifier, ConnectionType.UNIX_SOCKET, Constants.MQTT_MSG_BROKER_SOCKET)
    
    @staticmethod
    def create_mqtt_network_dev(identifier:str) -> MqttClient:
        return MqttClient(identifier, ConnectionType.TCP_DEBUG, "localhost")
    