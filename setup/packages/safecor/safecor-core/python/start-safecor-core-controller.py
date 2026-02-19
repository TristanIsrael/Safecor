from safecor import Dom0Controller, MqttFactory, SysLogger

if __name__ == "__main__":
    SysLogger("Safecor core controller").info("Starting core controller...")

    mqtt_client = MqttFactory.create_mqtt_client_dom0("Core controller")

    ctrl = Dom0Controller(mqtt_client)
    ctrl.start()

    SysLogger("Safecor core controller").warn("Core controller finished")