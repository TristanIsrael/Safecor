import unittest
from safecor import RequestFactory, Constants


class TestRequestFactory(unittest.TestCase):

    def test_create_request_files_list(self):
        payload = RequestFactory.create_request_files_list("disk1", True, "/sub", ["*.txt"])
        self.assertEqual(payload, {
            "disk": "disk1",
            "recursive": True,
            "from_dir": "/sub",
            "name_filters": ["*.txt"],
        })

    def test_create_request_files_list_defaults(self):
        payload = RequestFactory.create_request_files_list("disk1")
        self.assertEqual(payload, {
            "disk": "disk1",
            "recursive": False,
            "from_dir": "",
            "name_filters": "",
        })

    def test_create_request_read_file(self):
        self.assertEqual(
            RequestFactory.create_request_read_file("disk1", "/a/b.txt"),
            {"disk": "disk1", "filepath": "/a/b.txt"}
        )

    def test_create_request_copy_file(self):
        self.assertEqual(
            RequestFactory.create_request_copy_file("disk1", "/a.txt", "disk2"),
            {"disk": "disk1", "filepath": "/a.txt", "destination": "disk2"}
        )

    def test_create_request_delete_file(self):
        payload = RequestFactory.create_request_delete_file("/a/b.txt")
        self.assertEqual(payload, {"filepath": "/a/b.txt", "disk": Constants.STR_REPOSITORY})

        payload = RequestFactory.create_request_delete_file("/a/b.txt", "disk2")
        self.assertEqual(payload, {"filepath": "/a/b.txt", "disk": "disk2"})

    def test_create_request_start_benchmark(self):
        self.assertEqual(RequestFactory.create_request_start_benchmark("files"), {"module": "files"})

    def test_create_request_get_file_fingerprint(self):
        self.assertEqual(
            RequestFactory.create_request_get_file_fingerprint("/a.txt", "disk1"),
            {"filepath": "/a.txt", "disk": "disk1"}
        )

    def test_create_request_create_file(self):
        payload = RequestFactory.create_request_create_file("/a.txt", "disk1", b"hello world")
        self.assertEqual(payload, {
            "filepath": "/a.txt",
            "disk": "disk1",
            "data": "hello world",
            "compressed": False,
        })

        payload = RequestFactory.create_request_create_file("/a.txt", "disk1", b"hello", compressed=True)
        self.assertTrue(payload["compressed"])

    def test_create_request_restart_domain(self):
        self.assertEqual(RequestFactory.create_request_restart_domain("sys-usb"), {"domain_name": "sys-usb"})

    def test_create_request_ping(self):
        payload = RequestFactory.create_request_ping(7, "src", "data", 1700000000000)
        self.assertEqual(payload, {"id": 7, "source": "src", "data": "data", "sent_at": 1700000000000})

    def test_create_request_set_log_level(self):
        self.assertEqual(RequestFactory.create_request_set_log_level(20), {"level": 20})

    def test_create_request_save_log(self):
        self.assertEqual(
            RequestFactory.create_request_save_log("disk1", "log.txt"),
            {"disk": "disk1", "filename": "log.txt"}
        )

    def test_create_request_mount_file(self):
        self.assertEqual(
            RequestFactory.create_request_mount_file("disk1", "/a.iso"),
            {"disk": "disk1", "filepath": "/a.iso"}
        )

    def test_create_request_unmount(self):
        self.assertEqual(RequestFactory.create_request_unmount("disk1"), {"disk": "disk1"})

    def test_create_request_set_language(self):
        self.assertEqual(RequestFactory.create_request_set_language("fr"), {"language": "fr"})

    def test_create_request_switch_gui(self):
        self.assertEqual(RequestFactory.create_request_switch_gui("sys-gui"), {"domain": "sys-gui"})


if __name__ == "__main__":
    unittest.main()
