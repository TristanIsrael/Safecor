import unittest
from safecor import ResponseFactory, ComponentState, BenchmarkId


class TestResponseFactory(unittest.TestCase):

    def test_create_entry_component_state(self):
        entry = ResponseFactory.create_entry_component_state("id", "label", "name", ComponentState.STARTING, "core")

        self.assertEqual(entry.get("id", ""), "id")
        self.assertEqual(entry.get("label", ""), "label")
        self.assertEqual(entry.get("domain_name", ""), "name")
        self.assertEqual(entry.get("state", ""), ComponentState.STARTING.value)
        self.assertEqual(entry.get("type", ""), "core")

    def test_create_entry_component_state_default_type(self):
        entry = ResponseFactory.create_entry_component_state("id", "label", "name", ComponentState.READY)
        self.assertEqual(entry.get("type", ""), "core")

    def test_create_response_component_state(self):
        entry1 = ResponseFactory.create_entry_component_state("id1", "label1", "name1", ComponentState.STARTING, "core")
        entry2 = ResponseFactory.create_entry_component_state("id2", "label2", "name2", ComponentState.ERROR, "business")
        entry3 = ResponseFactory.create_entry_component_state("id3", "label3", "name3", ComponentState.READY, "core")

        payload = ResponseFactory.create_response_component_state([entry1, entry2, entry3])

        self.assertEqual(len(payload.get("components", [])), 3)

        entry1_ = payload["components"][0]
        entry2_ = payload["components"][1]
        entry3_ = payload["components"][2]

        self.assertEqual(entry1, entry1_)
        self.assertEqual(entry2, entry2_)
        self.assertEqual(entry3, entry3_)

    def test_create_response_disks_list(self):
        payload = ResponseFactory.create_response_disks_list(["disk1", "disk2"])
        self.assertEqual(payload, {"disks": ["disk1", "disk2"]})

        # Default empty list
        self.assertEqual(ResponseFactory.create_response_disks_list(), {"disks": []})

    def test_create_response_list_files(self):
        files = [{"type": "file", "name": "a"}]
        payload = ResponseFactory.create_response_list_files("disk1", files)
        self.assertEqual(payload, {"disk": "disk1", "files": files})

    def test_create_reponse_benchmark_inputs(self):
        payload = ResponseFactory.create_reponse_benchmark_inputs(10, 5)
        self.assertEqual(payload["id"], BenchmarkId.INPUTS)
        self.assertEqual(payload["duration"], 10)
        self.assertEqual(payload["iterations"], 5)

    def test_create_reponse_benchmark_fichiers_demarre(self):
        payload = ResponseFactory.create_reponse_benchmark_fichiers_demarre()
        self.assertEqual(payload, {"id": BenchmarkId.FILES, "state": "started"})

    def test_create_reponse_benchmark_fichiers_termine(self):
        metrics = [{"size": 1, "duration": 2}]
        payload = ResponseFactory.create_reponse_benchmark_fichiers_termine(metrics)
        self.assertEqual(payload["id"], BenchmarkId.FILES)
        # Note: the key is spelled "estatetat" in the implementation
        self.assertEqual(payload["estatetat"], "finished")
        self.assertEqual(payload["metrics"], metrics)

    def test_create_reponse_benchmark_fichiers_erreur(self):
        payload = ResponseFactory.create_reponse_benchmark_fichiers_erreur("boom")
        self.assertEqual(payload, {"id": BenchmarkId.FILES, "state": "error", "message": "boom"})

    def test_create_response_file_fingerprint(self):
        payload = ResponseFactory.create_response_file_fingerprint("/a/b.txt", "disk1", "abc123")
        self.assertEqual(payload, {"filepath": "/a/b.txt", "disk": "disk1", "fingerprint": "abc123"})

    def test_create_response_create_file(self):
        payload = ResponseFactory.create_response_create_file("/a.txt", "disk1", "abc123", True)
        self.assertEqual(payload, {"filepath": "/a.txt", "disk": "disk1", "fingerprint": "abc123", "success": True})

    def test_create_response_copy_file_success(self):
        payload = ResponseFactory.create_response_copy_file("/a.txt", "disk1", True, "abc123")
        self.assertEqual(payload, {"filepath": "/a.txt", "status": "ok", "fingerprint": "abc123"})

    def test_create_response_copy_file_error(self):
        payload = ResponseFactory.create_response_copy_file("/a.txt", "disk1", False, "")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["fingerprint"], "")

    def test_create_response_shutdown_accepted(self):
        self.assertEqual(ResponseFactory.create_response_shutdown(True), {"state": "accepted", "reason": ""})
        self.assertEqual(ResponseFactory.create_response_shutdown(False), {"state": "refused", "reason": ""})

    def test_create_response_restart_domain(self):
        accepted = ResponseFactory.create_response_restart_domain("sys-usb", True, "")
        self.assertEqual(accepted, {"domain_name": "sys-usb", "state": "accepted", "reason": ""})

        refused = ResponseFactory.create_response_restart_domain("Dom0", False, "protected")
        self.assertEqual(refused, {"domain_name": "Dom0", "state": "refused", "reason": "protected"})

    def test_create_response_ping(self):
        payload = ResponseFactory.create_response_ping(42, "src", "data", 1234)
        self.assertEqual(payload, {"id": 42, "source": "src", "data": "data", "sent_at": 1234})

    def test_create_response_languages_list(self):
        self.assertEqual(ResponseFactory.create_response_languages_list(["en", "fr"]), {"languages": ["en", "fr"]})

    def test_create_response_language_default(self):
        self.assertEqual(ResponseFactory.create_response_language_default("fr"), {"language": "fr"})

    def test_create_response_get_setting(self):
        self.assertEqual(ResponseFactory.create_response_get_setting("key", "value"), {"key": "key", "value": "value"})

    def test_create_response_set_setting(self):
        self.assertEqual(ResponseFactory.create_response_set_setting("key", 5), {"key": "key", "value": 5})

    def test_create_response_switch_gui(self):
        self.assertEqual(
            ResponseFactory.create_response_switch_gui(True, ""),
            {"state": "accepted", "reason": ""}
        )
        self.assertEqual(
            ResponseFactory.create_response_switch_gui(False, "not available"),
            {"state": "refused", "reason": "not available"}
        )


if __name__ == "__main__":
    unittest.main()
