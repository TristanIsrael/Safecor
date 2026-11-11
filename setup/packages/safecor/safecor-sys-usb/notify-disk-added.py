"""Udev helper: publishes a disk-added notification over MQTT when a USB storage device is plugged in.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import sys
import threading

from safecor import Api, MqttFactory

if len(sys.argv) < 2:
    print(f"Argument missing : {sys.argv[0]} disk_name")
    exit(1)

name = sys.argv[1]

api_ready = threading.Event()


def on_api_connected():
    """Callback invoked when the MQTT API connection is established."""
    api_ready.set()


mqtt_client = MqttFactory.create_mqtt_client_domu("notify-disk-added")

api = Api()
api.add_ready_callback(on_api_connected)
api.start(mqtt_client)

api_ready.wait()

api.info(f"The disk {name} has been connected to the system.")
api.notify_disk_added(name)
api.stop()
mqtt_client.stop()
exit(0)
