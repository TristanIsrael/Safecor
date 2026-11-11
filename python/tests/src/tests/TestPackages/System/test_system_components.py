from enums import MessageLevel
from lib import AbstractTest


class TestSystemComponents(AbstractTest):
    name = "System components"
    description = (
        "This test verifies whether the system components are correctly sent by the API"
    )
    parallelizable = True

    def start(self) -> None:
        """Called when the test is started"""
        self._set_progress(0)
        self._send_message(self.tr("Test not implemented"), MessageLevel.Warning)
        self.finished.emit()

    def stop(self) -> None:
        """Called when the test must be stopped"""

    def is_success(self) -> bool:
        """Called to know the test result"""
