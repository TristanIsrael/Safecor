import unittest
from safecor import MqttFactory, MqttClient, ConnectionType, Constants


class TestMqttFactory(unittest.TestCase):

    def test_create_mqtt_client_domu(self):
        client = MqttFactory.create_mqtt_client_domu("sys-usb")
        self.assertIsInstance(client, MqttClient)
        self.assertEqual(client.identifier, "sys-usb")
        self.assertEqual(client.connection_type, ConnectionType.SERIAL_PORT)
        self.assertEqual(client.connection_string, Constants.SERIAL_PORT_MSG)

    def test_create_mqtt_client_dom0(self):
        client = MqttFactory.create_mqtt_client_dom0("dom0")
        self.assertIsInstance(client, MqttClient)
        self.assertEqual(client.identifier, "dom0")
        self.assertEqual(client.connection_type, ConnectionType.UNIX_SOCKET)
        self.assertEqual(client.connection_string, Constants.MQTT_MSG_BROKER_SOCKET)

    def test_create_mqtt_network_dev(self):
        client = MqttFactory.create_mqtt_network_dev("dev")
        self.assertIsInstance(client, MqttClient)
        self.assertEqual(client.identifier, "dev")
        self.assertEqual(client.connection_type, ConnectionType.TCP_DEBUG)
        self.assertEqual(client.connection_string, "localhost")


if __name__ == "__main__":
    unittest.main()
