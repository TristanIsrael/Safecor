from lib import AbstractTest
from enums import MessageLevel
from safecor import Api, Topics, ApiHelper, DiskState

class TestGetStoragesList(AbstractTest):

    name = "Storage notifications"
    description = ""
    parallelizable = True
    __payload = {}
    __step = 0

    def start(self) -> None:
        """ Called when the test is started """
        self._set_progress(0)
 
        Api().add_message_callback(self.__on_message)
        Api().add_subscription_callback(self.__on_ready)
        Api().subscribe(Topics.DISK_STATE)        

    def __on_ready(self, mid:str):
        # Ask the user to connect one storage
        self._send_message(self.tr("Please connect a storage now."), MessageLevel.User)
        self._send_message(self.tr("Waiting for a storage..."), MessageLevel.Information)
        self._set_waiting(True)
        self.__step = 1

    def stop(self) -> None:
        """ Called when the test must be stopped """
        pass

    def __on_message(self, topic:str, payload:dict):
        if topic == Topics.DISK_STATE:
            self.__payload = payload

        if self.__step == 1:
            self.__step2()

    def __step2(self):
        # Verify the storage data
        if len(self.__payload) == {}:
            self._send_message(self.tr("Error: received a disk state notification but the disks list is empty"), MessageLevel.Error)
            self._set_finished(False)
            return
        elif self.__payload.get("disk", "") == "":
            self._send_message(self.tr("Error: received an empty disk name"), MessageLevel.Error)            
            self._set_finished(False)
            return
        else:                                
            if self.__payload.get("state", "") != "connected":
                self._send_message(self.tr("Error: the disk state is incorrect"), MessageLevel.Error)
                self._set_finished(False)
                return 
            
            # Use the API
            disk_name = ApiHelper.get_disk_name(self.__payload)
            disk_state = ApiHelper.get_disk_state(self.__payload)
            disk_connected = ApiHelper.is_disk_connected(self.__payload)

            if disk_name == "" or disk_state != DiskState.CONNECTED or not disk_connected or self.__payload.get("disk", "") != disk_name:
                self._send_message(self.tr("Error: the disk information return by ApiHelper is incorrect"), MessageLevel.Error)
                self._set_finished(False)
                return
            
        # The test is successful
        self._send_message(self.tr("The test succeeded"), MessageLevel.Information)
        self._set_finished(True)