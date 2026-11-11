from enums import MessageLevel
from lib import AbstractTest


class TestGetRepositoryFilesList(AbstractTest):
    name = "Get repository files list"
    description = ""
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
