#!/bin/python3

import sys
from pathlib import Path

from AppController import AppController
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import (
    QQmlApplicationEngine,
    qmlRegisterSingletonInstance,
)

"""class MyView(QQuickView):

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            # Ctrl+C has been pressed
            self.close()
            subprocess.run("poweroff")
        else:
            super().keyPressEvent(event)
"""


class CtrlCInterceptor(QObject):
    def eventFilter(self, _, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_C and (
                event.modifiers() & Qt.ControlModifier
                or event.modifiers() & Qt.MetaModifier
            ):
                print("Ctrl+C pressed")
                QGuiApplication.quit()
                # subprocess.run("poweroff")
                return True  # avoid propagation
        return False


def main():
    app = QGuiApplication(sys.argv)

    # signal.signal(signal.SIGINT, lambda *_: app.quit())

    # Expose QML Types
    qmlRegisterSingletonInstance(
        AppController, "net.alefbet", 1, 0, "AppController", AppController(app)
    )

    # Install font
    font = QFont("Roboto", 18)
    app.setFont(font)

    app_root_path = Path(__file__).parent
    engine = QQmlApplicationEngine()
    # view = MyView()

    # view.engine().quit.connect(app.quit)
    # view.engine().addImportPath(app_root_path / 'qml')
    engine.addImportPath(app_root_path / "qml")
    qml_file = app_root_path / "qml/main.qml"
    # view.setSource(qml_file.as_uri())
    engine.load(qml_file.as_uri())

    interceptor = CtrlCInterceptor()
    app.installEventFilter(interceptor)

    # if os.getenv("DEVMODE") is None:
    #    view.showFullScreen()
    # else:
    #    view.setWidth(800)
    #    view.setHeight(600)
    #    view.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
