from enums import MessageLevel
from lib import AbstractTest
from PySide6.QtCore import Slot


class TestMouse(AbstractTest):
    name = "Mouse"
    description = ""
    parallelizable = True

    def start(self) -> None:
        """Called when the test is started"""

        self._set_progress(0)
        self._send_message(self.tr("Please mouse the mouse"), MessageLevel.Warning)

    @Slot(str)
    def on_mouse_moved(self):
        """Called by AppController when the user moved the mouse"""

        if self.progress < 100:
            self._set_progress(100)
            self._send_message(
                self.tr("The mouse has been moved"), MessageLevel.Information
            )
            self.success = True
            self.finished.emit()

    def stop(self) -> None:
        """Called when the test must be stopped"""
