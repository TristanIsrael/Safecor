import unittest
import time
from safecor import DiskMonitor, Topics, MqttClient
from ._test_with_api import TestWithAPI

class FakeDevice():
    device_type = ""
    device_node = ""
    __values = {}

    def get(self, name):
        return self.__getitem__(name)

    def __getitem__(self, name):
        return self.__values.get(name, "")
    
    def __setitem__(self, name, value):
        self.__values[name] = value

class TestDiskMonitor(TestWithAPI):
    
    __device = FakeDevice()
    __device.device_type = "partition"
    __device.device_node = "No Name"
    __device["ID_FS_LABEL"] = "No Name"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.__monitor = DiskMonitor("/mnt", cls.mqtt_client)

    def test_start(self):
        try:
            self.__monitor.start()
        except ImportError:
            print("Cannot run this test on that machine")
            self.assertTrue(True) # Bypass

        self.__monitor.stop()

    def test_connect_storage(self):
        cls = self.__class__
        
        cls.mqtt_client.unsubscribe_all()
        cls.mqtt_client.subscribe(Topics.DISK_STATE)        
        
        cls.clear_messages()
        self.__monitor.device_event("add", self.__device)
        time.sleep(1)

        self.assertEqual(len(cls.messages), 1)
        message = cls.messages[0]
        self.assertEqual(message["topic"], Topics.DISK_STATE)
        self.assertEqual(message["payload"], { "disk": "No Name", "state": "connected" })

    def test_disconnect_storage(self):
        cls = self.__class__
        cls.clear_messages()

        self.__monitor.device_event("remove", self.__device)
        time.sleep(1)

        self.assertEqual(len(cls.messages), 1)
        message = cls.messages[0]
        self.assertEqual(message["topic"], Topics.DISK_STATE)
        self.assertEqual(message["payload"], { "disk": "No Name", "state": "disconnected" })

if __name__ == "__main__":
    unittest.main()