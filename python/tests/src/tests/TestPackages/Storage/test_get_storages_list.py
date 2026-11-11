from enums import MessageLevel
from lib import AbstractTest
from PySide6.QtCore import QTimer
from safecor import Api, ApiHelper, Topics


class TestGetStoragesList(AbstractTest):
    name = "Get storages list"
    description = ""
    parallelizable = True
    __payload = {}
    __step = 0
    __nb_notif_recv = 0
    __nb_disks = 0
    __disks_recv = []
    __tries = 0

    def start(self) -> None:
        """Called when the test is started"""
        self._set_progress(0)

        Api().add_message_callback(self.__on_message)
        Api().add_subscription_callback(self.__on_ready)
        Api().subscribe(Topics.DISK_STATE)
        Api().subscribe(f"{Topics.LIST_DISKS}/response")

    def __on_ready(self, mid: str):
        # Ask the user to connect one storage
        self._send_message(
            self.tr("Please connect a storage with multiple partitions now."),
            MessageLevel.User,
        )
        self._send_message(
            self.tr("Waiting for a storage..."), MessageLevel.Information
        )
        self._set_waiting(True)
        self.__step = 1

    def stop(self) -> None:
        """Called when the test must be stopped"""

    def __on_message(self, topic: str, payload: dict):
        if topic == Topics.DISK_STATE or topic == f"{Topics.LIST_DISKS}/response":
            self.__payload = payload

        if self.__step == 1:
            self.__step2()

    def __step2(self):
        # Verify the storage data
        if len(self.__payload) == {}:
            self._send_message(
                self.tr(
                    "Error: received a disk state notification but the disks list is empty"
                ),
                MessageLevel.Error,
            )
            self._set_finished(False)
            return
        elif self.__payload.get("disk", "") == "":
            self._send_message(
                self.tr("Error: received an empty disk name"), MessageLevel.Error
            )
            self._set_finished(False)
            return
        else:
            if self.__payload.get("state", "") != "connected":
                self._send_message(
                    self.tr("Error: the disk state is incorrect"), MessageLevel.Error
                )
                self._set_finished(False)
                return

            self.__nb_notif_recv = self.__nb_notif_recv + 1
            disk = ApiHelper.get_disk_name(self.__payload)
            self._send_message(
                self.tr(f"Received a notification for the disk {disk}"),
                MessageLevel.Information,
            )
            self.__disks_recv.append(disk)

            # Use the API
            Api().get_disks_list()

            QTimer.singleShot(100, self.__final_check)

    def __final_check(self):
        # If we have as much notifications as disks names, the test is ok
        # Otherwise we wait a little and check it one more time
        disks = self.__payload.get("disks", [])
        self.__nb_disks = len(disks) if disks is not None else 0

        if self.__nb_disks == self.__nb_notif_recv:
            # The test is successful
            self._send_message(self.tr("The test succeeded"), MessageLevel.Information)
            self._set_finished(True)
        elif self.__tries < 2:
            # Try again later
            QTimer.singleShot(100, self.__final_check)
        else:
            # The test has failed
            self._send_message(self.tr("The test has failed"), MessageLevel.Error)
            self._set_finished(False)
