import queue

from safecor import Api, MqttHelper, Topics
from Topics import TOPIC_RESPONSE, TOPIC_STEP


class Composant2:
    __messages_queue = queue.Queue()  # Queue is thread-safe

    def __init__(self):
        self.__system_uuid = None

    def start(self, mqtt_client):
        Api().subscribe(f"{TOPIC_STEP}/#")
        Api().subscribe(f"{Topics.SYSTEM_INFO}/response")
        Api().add_message_callback(self.__on_message_recv)

    def __on_message_recv(self, topic: str, payload: dict):
        if topic.startswith(TOPIC_STEP):
            self.__handle_step(payload)
        elif topic == f"{Topics.SYSTEM_INFO}/response":
            # If we queried the system information
            self.__handle_system_info(payload)

    def __handle_step(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["message"]):
            Api().error("Error #11 : message malformed")
            return

        message = payload.get("message", "")
        self.__messages_queue.put(message)

        # If we don't already have the CPU count we ask for it
        if self.__system_uuid is None:
            Api().request_system_info()
        else:
            # Otherwise we send the response
            self.__finish_step()

    def __handle_system_info(self, payload: dict):
        if MqttHelper.check_payload(payload, ["system"]):
            # Information is at system.machine.uuid
            system = payload.get("system", {})
            self.__system_uuid = system.get("uuid", 1)

            # now we send the message back
            self.__finish_step()
        else:
            Api().error("#12 : message malformed")

    def __finish_step(self):
        # We may have multiple messages in the queue
        while not self.__messages_queue.empty():
            message = self.__messages_queue.get()

            try:
                payload = {
                    "message": f"Original: {message}. System UUID={self.__system_uuid}"
                }
                Api().publish(TOPIC_RESPONSE, payload)
            except queue.Empty:
                break
