from safecor import Dom0Controller, MqttFactory

if __name__ == "__main__":
    mqtt_client = MqttFactory.create_mqtt_network_dev("Dom0")
    dom0 = Dom0Controller(mqtt_client)
    dom0.start()
