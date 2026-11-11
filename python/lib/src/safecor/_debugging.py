"""Debugging utilities

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import random
import string
import threading
from datetime import datetime

from . import Api, System, Topics


class Debugging:
    """
    This class provides facilities for product debugging.

    Before using the functions of this class you have to start the API.

    .. seealso::
        - :class:`Api` - API Documentation
    """

    __callback_benchmark_messaging = None
    __ping_responses = []
    __pings_sent = 0
    __iterations = 0
    __callback_fn = None
    __target_domain = ""
    __max_data_size_in_bytes = 32
    __ping_average = {}
    __ping_total = {}
    __subscriptions = []

    def benchmark_messaging(
        self,
        target_domain: str,
        callback_fn,
        iterations: int = 100,
        max_data_size_in_bytes: int = 1024,
    ):
        """
        Sends ping requests to a specific Domain, verifies the data and measure the performance.

        The payload will be randomly generated.
        The requests are all sent in one time, in a *bruteforce* style.

        **The API must be ready**.

        Args:
            target_domain(str): The name of the Domain which will receive the messages.
            callback_fn(Callable): The function which will receive the results of the benchmark.
            iterations(int, optional): The number of iterations for the test. Default is 100.
            max_data_size_in_bytes(int, optional): The maximum length of data generated.
        """
        self.__target_domain = target_domain
        self.__callback_fn = callback_fn
        self.__iterations = iterations
        self.__max_data_size_in_bytes = max_data_size_in_bytes
        self.__subscriptions = []

        # Subscribe to the Ping response topic
        Api().add_subscription_callback(self.__on_subscribed)
        Api().add_message_callback(self.__on_message_received)
        success, mid = Api().subscribe(f"{Topics.PING}/{System.domain_name()}/response")
        if success:
            self.__subscriptions.append(mid)

    def __on_subscribed(self, mid):
        if mid in self.__subscriptions:
            self.__do_benchmark_messaging()

    def __do_benchmark_messaging(self):
        self.__callback_benchmark_messaging = self.__callback_fn
        self.__pings_sent = 0
        self.__ping_average = {}
        self.__ping_total = {}
        self.__ping_responses = []

        self.__iterate()

    def __iterate(self):
        if self.__pings_sent < self.__iterations:
            chars = string.ascii_letters + string.digits
            data = "".join(random.choices(chars, k=self.__max_data_size_in_bytes))

            Api().ping(self.__target_domain, data)
            self.__pings_sent += 1

    def __on_message_received(self, topic: str, payload: dict):
        if topic == f"{Topics.PING}/{System.domain_name()}/response":
            payload["received_at"] = datetime.now().timestamp() * 1000
            self.__ping_responses.append(payload)
            threading.Thread(
                target=self.__handle_ping_response, args=(payload,)
            ).start()

    def __handle_ping_response(self, payload: dict):
        """
        Handles the response to Ping request

        When a reponse arrives, we evaluate the delay and verify the result. Then we call the callback to provide the results
        """

        if self.__callback_benchmark_messaging is None:
            # Do nothing if there is no callback
            return

        # We take the iterations and make some calculation
        data_length = len(payload["data"])
        delay_millis = payload["received_at"] - payload["sent_at"]
        data_rate_in_bytes_per_second = data_length / max(1, delay_millis * 1000)

        # We calculate the total values
        total_data_length = self.__ping_total.get("data_length", 0) + data_length
        # oldest_request = min(self.__ping_total.get("oldest_request"), payload["sent_at"]) if self.__ping_total.get("oldest_request") else payload["sent_at"]
        # youngest_response = max(self.__ping_total.get("youngest_response"), payload["received_at"]) if self.__ping_total.get("youngest_response") else payload["received_at"]
        total_delay = self.__ping_total.get("delay_in_millis", 0) + delay_millis
        data_rate = total_data_length / max(1, total_delay)

        self.__ping_total = {
            "data_length": total_data_length,
            "delay_in_millis": total_delay,
            "data_rate_in_bytes_per_second": data_rate,
        }

        # We calculate the average values
        avg_data_length = total_data_length / max(1, len(self.__ping_responses))
        avg_delay_in_millis = self.__ping_total.get("delay_in_millis", 0) / max(
            1, len(self.__ping_responses)
        )
        avg_data_rate = total_data_length / max(1, self.__ping_total["delay_in_millis"])

        self.__ping_average = {
            "data_length": avg_data_length,
            "delay_in_millis": avg_delay_in_millis,
            "data_rate_in_bytes_per_second": avg_data_rate,
        }

        result = {
            "pings_sent": self.__pings_sent,
            "pings_received": len(self.__ping_responses),
            "iteration": {
                "data_length": data_length,
                "delay_in_millis": delay_millis,
                "data_rate_in_bytes_per_second": data_rate_in_bytes_per_second,
            },
            "average": self.__ping_average,
            "total": self.__ping_total,
        }

        self.__callback_benchmark_messaging(result)
        threading.Timer(0.1, self.__iterate).start()
