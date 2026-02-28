from PySide6.QtCore import Slot
from lib import AbstractTest
from enums import MessageLevel

class TestTouch(AbstractTest):

    name = "Touchscreen"
    description = ""
    parallelizable = True

    def start(self) -> None:
        """ Called when the test is started """

        self._set_progress(0)
        self._send_message(self.tr("Please touch the screen"), MessageLevel.Warning)

    @Slot(str)
    def on_screen_touched(self):
        """ Called by AppController when the user touches the screen """

        if self.progress < 100:            
            self._set_progress(100)
            self._send_message(self.tr("The screen has been touched"), MessageLevel.Information)
            self.success = True
            self.finished.emit()

    def stop(self) -> None:
        """ Called when the test must be stopped """