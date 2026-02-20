#!/bin/python3

import os
import signal
import pkgutil
from pathlib import Path
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QKeyEvent, QGuiApplication, QFont, QFontDatabase
from PySide6.QtQuick import QQuickView
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType, qmlRegisterSingletonType, qmlRegisterUncreatableType, qmlRegisterSingletonInstance
from app_controller import AppController
from safecor import Api

class MyView(QQuickView):
    def keyPressEvent(self, event: QKeyEvent):
        # print(event.modifiers(), Qt.ControlModifier, event.key())
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            # Ctrl+C has been pressed
            self.close()
            QGuiApplication.quit()
        else:
            super().keyPressEvent(event)

def main():
    app = QGuiApplication(sys.argv)

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    
    # Expose QML Types
    qmlRegisterSingletonInstance(AppController, "Safecor", 1, 0, 'AppController', AppController(app))
            
    app_root_path = Path(__file__).parent

    # Install font Google Material
    font_file = app_root_path / "fonts/MaterialSymbolsOutlined-VariableFont_FILL,GRAD,opsz,wght.ttf"
    font_id = QFontDatabase.addApplicationFont(font_file.as_posix())

    if font_id != -1:
        print("The font Google Material has been correctly installed")
    else:
        print(f"The font Google Material has not been installed. Font path={font_file}")

    view = MyView()
    
    view.engine().quit.connect(app.quit)
    view.engine().addImportPath(app_root_path / 'qml')
    qml_file = app_root_path / 'qml/content/MainScreen.qml'
    view.setSource(qml_file.as_uri())
    if os.getenv("DEVMODE") is None:
        view.showFullScreen()
    else:
        view.show()

    Api().notify_gui_ready()

    return app.exec()

if __name__ == '__main__':
    sys.exit(main())
