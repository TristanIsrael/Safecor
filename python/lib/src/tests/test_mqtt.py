from safecor import MqttClient, ConnectionType, Topics, ResponseFactory
import unittest, time, threading

class TestMqttClient(unittest.TestCase):

    __recv_strings = []
    nb_connections = 0
    finished = False

    def setupConnection(self):
        if self.nb_connections == 0:
            print("Setting up client 1")
            self.client1 = MqttClient("test_client1", ConnectionType.TCP_DEBUG)
            self.client1.on_connected = self.__increment_connexions
            self.client1.on_message = self.__on_message
            self.client1.start()

            print("Setting up client 2")
            self.client2 = MqttClient("test_client2", ConnectionType.TCP_DEBUG)
            self.client2.on_connected = self.__increment_connexions
            self.client2.on_message = self.__on_message
            self.client2.start()

            time.sleep(0.5)

    def setUp(self):
        if self._testMethodName == "test_connections_count":
            self.setupConnection()
        elif self._testMethodName == "test_list_disks":
            self.setupConnection()
            self.client2.subscribe(f"{Topics.LIST_DISKS}/request")
            time.sleep(0.5)
        elif self._testMethodName == "test_list_files":
            self.setupConnection()
            self.client2.subscribe(f"{Topics.LIST_FILES}/request")
            time.sleep(0.5)
        elif self._testMethodName == "test_utf8":
            self.setupConnection()
            self.client1.subscribe("test/utf8")
            time.sleep(0.5)

    def test_connections_count(self):
        print("Testing connections count")
        self.assertEqual(self.nb_connections, 2)

    def test_list_disks(self):
        print("Testing disks list")
        self.finished = False
        time.sleep(0.5)
        self.client2.subscribe(f"{Topics.LIST_DISKS}/request")
        self.client1.subscribe(f"{Topics.LIST_DISKS}/response")
        self.client1.publish(f"{Topics.LIST_DISKS}/request", {})
        time.sleep(0.5)
        self.assertTrue(self.finished)

    def test_list_files(self):
        print("Testing files list")
        self.finished = False
        self.client2.subscribe(f"{Topics.LIST_FILES}/request")
        self.client1.subscribe(f"{Topics.LIST_FILES}/response")
        self.client1.publish(f"{Topics.LIST_FILES}/request", { "disk": "disk 1" })
        time.sleep(1)
        self.assertTrue(self.finished)

    def __increment_connexions(self):
        self.nb_connections += 1

    def __on_message(self, topic:str, payload:dict):
        print(topic)
        if self._testMethodName == "test_list_disks":
            if topic == f"{Topics.LIST_DISKS}/request":
                response = ResponseFactory.create_response_disks_list([ "disk 1", "disk 2" ])
                self.client2.publish(f"{Topics.LIST_DISKS}/response", response)
            elif topic == f"{Topics.LIST_DISKS}/response":
                disks = payload.get("disks")
                self.assertIsNotNone(disks)
                self.assertEqual(len(disks), 2)
                self.assertEqual(disks[0], "disk 1")
                self.assertEqual(disks[1], "disk 2")
                self.finished = True
        elif self._testMethodName == "test_list_files":
            if topic == f"{Topics.LIST_FILES}/request":
                self.assertEqual(payload.get("disk"), "disk 1")
                files = [
                    { "path": "/", "name": "file 1.txt", "size": 123, "type": "file" },
                    { "path": "/", "name": "file 2.exe", "size": 18882726, "type": "file" },
                    { "path": "/", "name": "תיק", "type": "folder" }
                ]
                response = ResponseFactory.create_response_list_files("disk 1", files)
                self.client2.publish(f"{Topics.LIST_FILES}/response", response)
            elif topic == f"{Topics.LIST_FILES}/response":
                disk = payload.get("disk")
                self.assertIsNotNone(disk)
                self.assertEqual(disk, "disk 1")
                files = payload.get("files")
                self.assertEqual(len(files), 3)
                self.assertEqual(files[0].get("path"), "/")
                self.assertEqual(files[1].get("path"), "/")
                self.assertEqual(files[2].get("path"), "/")
                self.assertEqual(files[0].get("name"), "file 1.txt")
                self.assertEqual(files[1].get("name"), "file 2.exe")
                self.assertEqual(files[2].get("name"), "תיק")
                self.assertEqual(files[0].get("size"), 123)
                self.assertEqual(files[1].get("size"), 18882726)
                self.assertIsNone(files[2].get("size"))
                self.assertEqual(files[0].get("type"), "file")
                self.assertEqual(files[1].get("type"), "file")
                self.assertEqual(files[2].get("type"), "folder")
                self.finished = True
        elif self._testMethodName == "test_utf8":
            self.__recv_strings.append(payload["string"])

                
    def test_utf8(self):
        test_strings = [
            "1. A string without special chars",
            "2. Accents et symboles : éàèùâêîôû ç ñ ä ö ü ß € £ ¥ © ® ™",
            "3. 日本語テスト：システムガイド保守マニュアル version1.0",
            "4. בדיקת יוניקוד: מערכת-מדריך-תחזוקה גרסה 1.0"
        ]        

        for s in test_strings:
            self.client2.publish("test/utf8", { "string": s })

        time.sleep(0.5)

        self.assertEqual(self.__recv_strings, test_strings)
        print(self.__recv_strings)


    def tearDown(self):
        self.client1.stop()
        del self.client1
        self.client2.stop()
        del self.client2

if __name__ == "__main__":    
    unittest.main()