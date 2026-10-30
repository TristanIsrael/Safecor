import unittest
import json
import types
import unittest.mock as mock

from safecor import MqttClient, ConnectionType
import safecor._mqtt_client as _mqtt_client


class TestMqttClient(unittest.TestCase):

    def setUp(self):
        # Avoid real syslog calls if a warn/error path is exercised
        patcher = mock.patch.object(_mqtt_client, "SysLogger")
        self.mock_syslogger = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = MqttClient("client_id")

    def _fake_msg(self, payload, topic="some/topic"):
        return types.SimpleNamespace(topic=topic, payload=json.dumps(payload).encode("utf-8"))

    # --- construction ----------------------------------------------------

    def test_construction_default(self):
        self.assertEqual(self.client.identifier, "client_id")
        self.assertEqual(self.client.connection_type, ConnectionType.UNIX_SOCKET)
        self.assertIsNone(self.client.mqtt_client)
        self.assertFalse(self.client.connected)

    def test_construction_tcp(self):
        client = MqttClient("id", ConnectionType.TCP_DEBUG, "localhost")
        self.assertEqual(client.connection_type, ConnectionType.TCP_DEBUG)
        self.assertEqual(client.connection_string, "localhost")

    def test_get_transport_type(self):
        get = self.client._MqttClient__get_transport_type
        self.assertEqual(MqttClient("i", ConnectionType.TCP_DEBUG)._MqttClient__get_transport_type(), "tcp")
        self.assertEqual(MqttClient("i", ConnectionType.UNIX_SOCKET)._MqttClient__get_transport_type(), "unix")
        self.assertEqual(get(), "unix")

    # --- callback registration -------------------------------------------

    def test_message_callback_registration(self):
        cb = lambda t, p: None
        self.client.add_message_callback(cb)
        self.assertIn(cb, self.client._MqttClient__message_callbacks)
        # reset clears them
        self.client.reset_message_callbacks()
        self.assertEqual(self.client._MqttClient__message_callbacks, [])

    def test_del_message_callback(self):
        cb = lambda t, p: None
        self.client.add_message_callback(cb)
        self.assertIn(cb, self.client._MqttClient__message_callbacks)
        self.client.del_message_callback(cb)
        self.assertNotIn(cb, self.client._MqttClient__message_callbacks)

    def test_connected_callback_registration(self):
        cb = lambda: None
        self.client.add_connected_callback(cb)
        self.assertIn(cb, self.client._MqttClient__connected_callbacks)

    # --- message dispatch ------------------------------------------------

    def test_on_message_dispatches(self):
        received = []
        self.client.on_message = lambda topic, payload: received.append(("on_message", topic, payload))
        self.client.add_message_callback(lambda topic, payload: received.append(("cb", topic, payload)))

        payload = {"hello": "world"}
        self.client._MqttClient__on_message(None, None, self._fake_msg(payload, "t/x"))

        self.assertIn(("on_message", "t/x", payload), received)
        self.assertIn(("cb", "t/x", payload), received)

    def test_on_message_bad_payload_ignored(self):
        received = []
        self.client.on_message = lambda topic, payload: received.append(payload)

        bad = types.SimpleNamespace(topic="t", payload=b"this is not json")
        self.client._MqttClient__on_message(None, None, bad)

        self.assertEqual(received, [])
        # A warning was logged about the uncaught exception
        self.assertTrue(self.mock_syslogger.return_value.warn.called)

    # --- connection events -----------------------------------------------

    def test_on_connected(self):
        received = []
        self.client.on_connected = lambda: received.append("on_connected")
        self.client.add_connected_callback(lambda: received.append("cb"))

        self.client._MqttClient__on_connected(None, None, None, None, None)

        self.assertTrue(self.client.connected)
        self.assertFalse(self.client.is_starting)
        self.assertIn("on_connected", received)
        self.assertIn("cb", received)

    def test_on_connected_first_connection_is_a_no_op(self):
        # No subscription was tracked yet: nothing to re-apply and the
        # (not yet created) paho client must not be touched.
        self.client._MqttClient__on_connected(None, None, None, None, None)
        self.assertIsNone(self.client.mqtt_client)

    def test_on_connected_resubscribes_tracked_topics(self):
        # Simulate a reconnection: the client was subscribed before the
        # connection was lost, a new paho client was created, and the
        # connect event fires again.
        self.client.mqtt_client = mock.MagicMock()  # the initial paho client
        self.client.subscribe("topic/a")
        self.client.subscribe("topic/b")
        self.client.subscribe("topic/a")  # duplicated on purpose

        self.client.mqtt_client = mock.MagicMock()  # the new paho client

        self.client._MqttClient__on_connected(None, None, None, None, None)

        calls = self.client.mqtt_client.subscribe.call_args_list
        resubscribed = [c.args[0] for c in calls]
        self.assertEqual(resubscribed, ["topic/a", "topic/b"])
        # The tracking list must not be polluted by the re-application
        self.assertEqual(
            self.client._MqttClient__subscriptions, ["topic/a", "topic/b", "topic/a"]
        )

    def test_on_subscribe(self):
        received = []
        self.client.on_subscribed = lambda mid: received.append(mid)
        self.client._MqttClient__on_subscribe(None, None, 7, None, None)
        self.assertEqual(received, [7])

    def test_on_log(self):
        received = []
        self.client.on_log = lambda level, buf: received.append((level, buf))
        self.client._MqttClient__on_log(None, None, 1, "msg")
        self.assertEqual(received, [(1, "msg")])

    def test_on_disconnected(self):
        # Should not raise
        self.client._MqttClient__on_disconnected(None)

    # --- publish / subscribe (mock transport) ----------------------------

    def test_publish(self):
        self.client.mqtt_client = mock.MagicMock()
        self.client.publish("some/topic", {"a": 1})
        self.client.mqtt_client.publish.assert_called_with(topic="some/topic", payload='{"a": 1}')

    def test_subscribe(self):
        self.client.mqtt_client = mock.MagicMock()
        self.client.subscribe("t1")
        self.client.subscribe("t2")
        self.assertEqual(self.client.mqtt_client.subscribe.call_count, 2)
        self.assertEqual(self.client._MqttClient__subscriptions, ["t1", "t2"])

    def test_unsubscribe(self):
        self.client.mqtt_client = mock.MagicMock()
        self.client.subscribe("t1")
        self.client.unsubscribe("t1")
        self.client.mqtt_client.unsubscribe.assert_called_once_with("t1")
        self.assertEqual(self.client._MqttClient__subscriptions, [])

    def test_unsubscribe_all(self):
        self.client.mqtt_client = mock.MagicMock()
        self.client.subscribe("t1")
        self.client.unsubscribe_all()
        self.assertEqual(self.client.mqtt_client.unsubscribe.call_count, 1)
        self.assertEqual(self.client._MqttClient__subscriptions, [])

    def test_stop(self):
        self.client.mqtt_client = mock.MagicMock()
        self.client.connected = True
        self.client.stop()
        self.client.mqtt_client.disconnect.assert_called_once()
        self.client.mqtt_client.loop_stop.assert_called_once()
        # Not a serial port, so close() must not be called
        self.client.mqtt_client.close.assert_not_called()
        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.is_starting)

    def test_stop_serial_calls_close(self):
        self.client.connection_type = ConnectionType.SERIAL_PORT
        self.client.mqtt_client = mock.MagicMock()
        self.client.stop()
        self.client.mqtt_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
