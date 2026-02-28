from lib import AbstractTest
from enums import MessageLevel

class TestSerialPort(AbstractTest):

    name = "Serial port"
    description = ""
    parallelizable = True

    def start(self) -> None:
        """ Called when the test is started """

        self._set_progress(100)
        self._send_message(self.tr("Test not implemented"), MessageLevel.Warning)
        self.success = True
        self.finished.emit()

    def stop(self) -> None:
        """ Called when the test must be stopped """
