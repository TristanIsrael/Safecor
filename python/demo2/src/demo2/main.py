#!/bin/python3

import os
import signal
import sys
from pathlib import Path

from AppController import AppController
from Composant1 import Composant1
from Composant2 import Composant2
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from safecor import MqttFactory

app = QGuiApplication(sys.argv)


def handle_sigint(signum, frame):
    app.quit()  # Quitte la boucle Qt


signal.signal(signal.SIGINT, handle_sigint)

if __name__ == "__main__":
    # On prépare le client MQTT
    if os.getenv("DEVMODE") is not None:
        # Dom0
        mqtt_client = MqttFactory.create_mqtt_network_dev("demo2")
    else:
        mqtt_client = MqttFactory.create_mqtt_client_domu("demo2")

    # Expose les Types QML
    qmlRegisterSingletonInstance(
        AppController,
        "net.alefbet",
        1,
        0,
        "AppController",
        AppController(app, mqtt_client),
    )

    app_root_path = Path(__file__).parent
    engine = QQmlApplicationEngine()
    engine.addImportPath(app_root_path / "qml")
    qml_file = app_root_path / "qml/main.qml"
    engine.load(qml_file.as_uri())

    if not engine.rootObjects():
        sys.exit(-1)

    qml_root = engine.rootObjects()[0]
    if os.getenv("DEVMODE") is None:
        qml_root.showFullScreen()

    # On démarre les composants en mode mock si nécessaire
    if os.getenv("DEVMODE") is not None:
        # Composants
        Composant1().start(mqtt_client)
        Composant2().start(mqtt_client)

    app.exec()
