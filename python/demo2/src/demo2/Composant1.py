import queue

from safecor import Api, MqttHelper, Topics
from Topics import TOPIC_REQUEST, TOPIC_STEP


class Composant1:
    __messages_queue = queue.Queue()  # Queue is thread-safe

    def __init__(self):
        self.__cpu_count = None

    def start(self, mqtt_client):
        Api().subscribe(TOPIC_REQUEST)
        Api().subscribe(f"{Topics.SYSTEM_INFO}/response")
        Api().add_message_callback(self.__on_message_recv)

    def __on_message_recv(self, topic: str, payload: dict):
        if topic == TOPIC_REQUEST:
            self.__handle_step_1(payload)
        elif topic == f"{Topics.SYSTEM_INFO}/response":
            # If we queried the system information
            self.__handle_system_info(payload)

    def __handle_step_1(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["message"]):
            Api().error("Error #11 : message malformed")
            return

        message = payload.get("message", "")
        self.__messages_queue.put(message)

        # If we don't already have the CPU count we ask for it
        if self.__cpu_count is None:
            Api().request_system_info()
        else:
            # Otherwise we send the response
            self.__finish_step_1()

    def __handle_system_info(self, payload: dict):
        if MqttHelper.check_payload(payload, ["system"]):
            # Information is at system.machine.cpu.count
            system = payload.get("system", {})
            machine = system.get("machine", {})
            cpu = machine.get("cpu", {})
            self.__cpu_count = cpu.get("count", 1)

            # now we send the message back
            self.__finish_step_1()
        else:
            Api().error("#12 : message malformed")

    def __finish_step_1(self):
        # We may have multiple messages in the queue
        while not self.__messages_queue.empty():
            message = self.__messages_queue.get()

            try:
                payload = {
                    "message": f"Original: {message}. CPU count={self.__cpu_count}"
                }
                Api().publish(f"{TOPIC_STEP}/1", payload)
            except queue.Empty:
                break
