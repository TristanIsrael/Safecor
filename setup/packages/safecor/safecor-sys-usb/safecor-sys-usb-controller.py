""" Entry point for the sys-usb Domain controller: manages USB storage passthrough and MQTT notifications.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from safecor import SysUsbController, MqttFactory
import threading

if __name__ == "__main__":
    mqtt_client = MqttFactory.create_mqtt_client_domu("sys-usb")

    lock = threading.Event()

    c=SysUsbController(mqtt_client)
    c.start()

    lock.wait()