import os
import tempfile

from MessagesFactory import MessagesFactory
from PySide6.QtCore import Property, QObject, Signal, Slot
from safecor import Api
from Topics import TOPIC_REQUEST, TOPIC_RESPONSE, TOPIC_STEP


class AppController(QObject):
    __ready = False
    __result = ""

    readyChanged = Signal()
    resultChanged = Signal()

    def __init__(self, parent, mqtt_client):
        super().__init__(parent)

        # Connect to the messaging system
        Api().add_ready_callback(self.__on_api_ready)
        Api().add_message_callback(self.__on_message_recv)
        Api().start(
            mqtt_client=mqtt_client,
            recording=True,
            logfile=tempfile.gettempdir() + os.path.sep + "demo2_gui.log",
        )

    ###
    #    Slots
    ###
    @Slot(str)
    def on_btn_start_clicked(self, message: str) -> None:
        Api().info(
            f"L'utilisateur a cliqué sur le bouton démarrer. Message : {message}"
        )
        payload = MessagesFactory.create_message_request(message)
        Api().publish(TOPIC_REQUEST, payload)

    ###
    #    Private fonctions
    ###
    def __on_api_ready(self):
        print("Safecor API is ready")

        # We subscribe to necessary topics
        Api().subscribe(f"{TOPIC_STEP}/#")
        Api().subscribe(TOPIC_RESPONSE)

        self.__ready = True
        self.readyChanged.emit()

    def __on_message_recv(self, topic: str, payload: dict):
        if topic.startswith(TOPIC_STEP) or topic == TOPIC_RESPONSE:
            self.__handle_message(payload)

    def __handle_message(self, payload: dict):
        message = payload.get("message", "Message vide...")
        self.__result += f"\n{message}" if self.__result != "" else message
        self.resultChanged.emit()

    ###
    #    Getters and setters
    ###
    def __is_ready(self):
        return self.__ready

    def __get_result(self):
        return self.__result

    ###
    #    Properties
    ###
    ready = Property(bool, __is_ready, notify=readyChanged)
    result = Property(str, __get_result, notify=resultChanged)
