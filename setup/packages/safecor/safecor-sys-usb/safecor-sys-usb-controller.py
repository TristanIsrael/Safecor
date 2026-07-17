from safecor import SysUsbController, MqttFactory
import threading

if __name__ == "__main__":
    mqtt_client = MqttFactory.create_mqtt_client_domu("sys-usb")

    lock = threading.Event()

    c = SysUsbController(mqtt_client)
    c.start()

    lock.wait()