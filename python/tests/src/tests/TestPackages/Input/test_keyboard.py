from PySide6.QtCore import Slot
from lib import AbstractTest
from enums import MessageLevel

class TestKeyboard(AbstractTest):

    name = "Keyboard"
    description = ""
    parallelizable = True    

    def start(self) -> None:
        """ Called when the test is started """

        self._set_progress(0)
        self._send_message(self.tr("Please type 'Safecor' on the keyboard"), MessageLevel.Warning)
        

    @Slot(str)
    def on_user_text_changed(self, text:str):
        """ Called by AppController when the user entered a text """

        if text.lower() == "safecor":
            self._set_progress(100)
            self._send_message(self.tr("The keyboard input has been received"), MessageLevel.Information)
            self.resetUserText.emit()
            self.success = True
            self.finished.emit()

    def stop(self) -> None:
        """ Called when the test must be stopped """
        
