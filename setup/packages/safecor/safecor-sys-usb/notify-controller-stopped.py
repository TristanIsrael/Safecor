import sys, threading
from safecor import Api, MqttFactory, ResponseFactory, Constants, ComponentState, Topics

api_ready = threading.Event()
def on_api_connected():
    api_ready.set()

mqtt_client = MqttFactory.create_mqtt_client_domu("sys-usb controller")

api = Api()
api.add_ready_callback(on_api_connected)
api.start(mqtt_client)

api_ready.wait()

api.info(f"The sys-usb controller has been stopped.")

# Publish the new state of the components
comp1 = ResponseFactory.create_entry_component_state(Constants.SAFECOR_DISK_CONTROLLER, "System disk controller", "sys-usb", ComponentState.OFF, "core")
comp2 = ResponseFactory.create_entry_component_state(Constants.SAFECOR_INPUT_CONTROLLER, "Input controller", "sys-usb", ComponentState.OFF, "core")
payload = ResponseFactory.create_response_component_state([comp1, comp2])
api.publish(f"{Topics.DISCOVER_COMPONENTS}/response", payload)

api.stop()
mqtt_client.stop()
exit(0)
