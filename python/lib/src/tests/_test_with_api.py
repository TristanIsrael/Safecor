import subprocess
import threading
import time
import unittest

import psutil

from safecor import MqttFactory


class TestWithAPI(unittest.TestCase):
    """This class helps handling the Safecor API in the unit tests"""

    @classmethod
    def is_mosquitto_running(cls):
        """Returns true if the MQTT broker mosquitto is currently running"""
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] == "mosquitto":
                return True
        return False

    @classmethod
    def setUpClass(cls):
        # Verify Mosquitto
        if not cls.is_mosquitto_running():
            cls.mosquitto_proc = subprocess.Popen(["mosquitto"])
            time.sleep(1)

            if not cls.is_mosquitto_running():
                raise RuntimeError("Mosquitto could not be started")
        else:
            cls.mosquitto_proc = None

        # Start Safecor MQTT client
        cls.setup_lock = threading.Event()
        cls.messages = []
        cls.mqtt_client = MqttFactory.create_mqtt_network_dev("test_logger")
        cls.mqtt_client.add_connected_callback(cls.on_mqtt_connected)
        cls.mqtt_client.add_message_callback(cls.on_message)
        cls.mqtt_client.start()
        if not cls.setup_lock.wait(1.0):
            raise RuntimeError("Could not connect to Safecor API")

    @classmethod
    def tearDownClass(cls):
        if cls.mosquitto_proc:
            cls.mosquitto_proc.terminate()
            cls.mosquitto_proc.wait()

        if cls.mqtt_client is not None:
            cls.mqtt_client.stop()
            del cls.mqtt_client

        # if os.path.exists("/tmp/safecor.log"):
        #    os.remove("/tmp/safecor.log")

    @classmethod
    def on_mqtt_connected(cls):
        """Triggered when the connexion to the broker has been established

        It sets the :class:`Logger` instance up and releases the lock created in :func:`setupClass`.
        """

        print("Connected to Safecor API")
        cls.setup_lock.set()

    @classmethod
    def on_message(cls, topic: str, payload: dict):
        """Triggered when a message is received. The message is appended to ``cls.messages`` list."""
        cls.messages.append({"topic": topic, "payload": payload})
        # print(cls.messages)

    @classmethod
    def clear_messages(cls):
        cls.messages.clear()
