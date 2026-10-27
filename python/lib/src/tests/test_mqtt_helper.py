import unittest
from safecor import MqttHelper


class TestMqttHelper(unittest.TestCase):

    def test_check_payload_all_keys_present(self):
        payload = {"a": 1, "b": 2, "c": 3}
        self.assertTrue(MqttHelper.check_payload(payload, ["a", "b", "c"]))

    def test_check_payload_subset(self):
        payload = {"a": 1, "b": 2}
        self.assertTrue(MqttHelper.check_payload(payload, ["a"]))

    def test_check_payload_missing_key(self):
        payload = {"a": 1}
        self.assertFalse(MqttHelper.check_payload(payload, ["a", "b"]))

    def test_check_payload_none_value(self):
        # A key that is present but None is treated as missing
        payload = {"a": None, "b": 2}
        self.assertFalse(MqttHelper.check_payload(payload, ["a", "b"]))

    def test_check_payload_empty_expected(self):
        self.assertTrue(MqttHelper.check_payload({}, []))
        self.assertTrue(MqttHelper.check_payload({"a": 1}, []))


if __name__ == "__main__":
    unittest.main()
