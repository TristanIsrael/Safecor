import unittest
import unittest.mock as mock

from safecor import Debugging, Topics
import safecor._debugging as _debugging


class TestDebugging(unittest.TestCase):

    def _new_debugger(self):
        d = Debugging()
        return d

    # --- benchmark_messaging setup ---------------------------------------

    def test_benchmark_messaging_subscribes(self):
        with mock.patch.object(_debugging, "Api", mock.MagicMock()) as api, \
             mock.patch.object(_debugging, "System", mock.MagicMock()) as system:
            system.domain_name.return_value = "me"
            api.return_value.subscribe.return_value = (True, 5)
            d = self._new_debugger()
            d.benchmark_messaging("target", lambda r: None)

            api.return_value.add_subscription_callback.assert_called_once()
            api.return_value.add_message_callback.assert_called_once()
            api.return_value.subscribe.assert_called_once_with(f"{Topics.PING}/me/response")

    # --- on_subscribed -> do_benchmark -> iterate ------------------------

    def test_on_subscribed_starts_benchmark(self):
        with mock.patch.object(_debugging, "Api", mock.MagicMock()) as api:
            d = self._new_debugger()
            d._Debugging__callback_fn = lambda r: None
            d._Debugging__iterations = 5
            d._Debugging__max_data_size_in_bytes = 8
            d._Debugging__target_domain = "target"
            d._Debugging__subscriptions = [1]

            d._Debugging__on_subscribed(1)

            # One ping is sent per iteration step
            self.assertEqual(d._Debugging__pings_sent, 1)
            api.return_value.ping.assert_called_once()

    def test_on_subscribed_ignores_unknown_mid(self):
        with mock.patch.object(_debugging, "Api", mock.MagicMock()) as api:
            d = self._new_debugger()
            d._Debugging__callback_fn = lambda r: None
            d._Debugging__iterations = 5
            d._Debugging__subscriptions = [1]

            d._Debugging__on_subscribed(999)  # not in subscriptions

            api.return_value.ping.assert_not_called()
            self.assertEqual(d._Debugging__pings_sent, 0)

    def test_iterate_sends_pings(self):
        with mock.patch.object(_debugging, "Api", mock.MagicMock()) as api:
            d = self._new_debugger()
            d._Debugging__iterations = 2
            d._Debugging__max_data_size_in_bytes = 8
            d._Debugging__target_domain = "target"
            d._Debugging__pings_sent = 0

            d._Debugging__iterate()
            d._Debugging__iterate()

            self.assertEqual(d._Debugging__pings_sent, 2)
            self.assertEqual(api.return_value.ping.call_count, 2)

    def test_iterate_stops_at_limit(self):
        with mock.patch.object(_debugging, "Api", mock.MagicMock()) as api:
            d = self._new_debugger()
            d._Debugging__iterations = 1
            d._Debugging__pings_sent = 1
            d._Debugging__max_data_size_in_bytes = 8
            d._Debugging__target_domain = "target"

            d._Debugging__iterate()

            self.assertEqual(d._Debugging__pings_sent, 1)
            api.return_value.ping.assert_not_called()

    # --- on_message_received ---------------------------------------------

    def test_on_message_received_appends_response(self):
        with mock.patch.object(_debugging, "System", mock.MagicMock()) as system, \
             mock.patch("threading.Thread", mock.MagicMock()) as thread:
            system.domain_name.return_value = "me"
            d = self._new_debugger()
            d._Debugging__ping_responses = []

            d._Debugging__on_message_received(
                f"{Topics.PING}/me/response", {"id": 1, "data": "x", "sent_at": 1000.0}
            )

            self.assertEqual(len(d._Debugging__ping_responses), 1)
            self.assertIn("received_at", d._Debugging__ping_responses[0])
            thread.return_value.start.assert_called_once()

    def test_on_message_received_ignores_other_topic(self):
        with mock.patch.object(_debugging, "System", mock.MagicMock()) as system, \
             mock.patch("threading.Thread", mock.MagicMock()) as thread:
            system.domain_name.return_value = "me"
            d = self._new_debugger()
            d._Debugging__ping_responses = []

            d._Debugging__on_message_received("some/other/topic", {"id": 1})

            self.assertEqual(d._Debugging__ping_responses, [])
            thread.assert_not_called()

    # --- handle_ping_response computation --------------------------------

    def test_handle_ping_response_computes_metrics(self):
        d = self._new_debugger()
        received = []
        d._Debugging__callback_benchmark_messaging = lambda r: received.append(r)
        d._Debugging__pings_sent = 3
        d._Debugging__ping_total = {}
        d._Debugging__ping_average = {}

        payload = {"data": "abcd", "sent_at": 1000.0, "received_at": 1100.0}
        d._Debugging__ping_responses = [payload]

        with mock.patch("threading.Timer", mock.MagicMock()) as timer:
            d._Debugging__handle_ping_response(payload)

        self.assertEqual(len(received), 1)
        result = received[0]
        self.assertEqual(result["pings_sent"], 3)
        self.assertEqual(result["pings_received"], 1)
        self.assertEqual(result["iteration"]["data_length"], 4)
        self.assertEqual(result["iteration"]["delay_in_millis"], 100.0)
        self.assertEqual(result["total"]["data_length"], 4)
        self.assertEqual(result["total"]["delay_in_millis"], 100.0)
        timer.return_value.start.assert_called_once()

    def test_handle_ping_response_no_callback(self):
        d = self._new_debugger()
        d._Debugging__callback_benchmark_messaging = None
        # Returns early without raising
        d._Debugging__handle_ping_response({"data": "x", "sent_at": 1.0, "received_at": 2.0})


if __name__ == "__main__":
    unittest.main()
