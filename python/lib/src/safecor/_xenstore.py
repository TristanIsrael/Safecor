import xen.lowlevel.xs
from threading import Thread
from enum import Enum

class XenStore:
    """ This class offers function to read and write to the XenStore """

    class XsDomain(Enum):
        System = "system"
        SysUsb = "sys-usb"

    class XsKey(Enum):
        InputFocus = "input-focus"

    __monitoring_callbacks = {}
    __monitoring_running = False

    def __init__(self):
        self.__xs = xen.lowlevel.xs.xs()

    def read(self, domain_name:str, key:str):
        """ Read information from the XenStore """

        dom_id = self.__get_domain_id(domain_name)

        return self.__xs.read(f"/local/domain/{dom_id}/{key}".encode())
    
    def read_path(self, key_path:str):
        """ Read information from the XenStore using a key path """

        return self.__xs.read(f"{key_path}".encode())

    def write(self, domain_name:str, key:str, value:str):
        """ Write information in the XenStore """

        dom_id = self.__get_domain_id(domain_name)

        self.__xs.write(f"/local/domain/{dom_id}/{key}".encode(), value)

    def monitor(self, domain_name:str, key:str, token:str, callback):
        """ Monitors a key in the XenStore and get notified in cas of a change """

        dom_id = self.__get_domain_id(domain_name)

        self.__xs.watch(f"/local/domain/{dom_id}/{key}".encode(), token.encode())
        self.__monitoring_callbacks[token] = callback
        
        if not self.__monitoring_running:
            Thread(target=self.__do_monitor).start()

    def __do_monitor(self):
        self.__monitoring_running = True

        while True:
            # Wait for a change
            path, token = self.__xs.read_watch()

            # Get the callback
            callback = self.__monitoring_callbacks[token]
            if callback is not None:
                # We get the value
                value = self.read_path(path)

                # Call the callback
                callback(value)

    def __get_domain_id(self, domain_name:str):
        _domain = ""

        if domain_name == XenStore.XsDomain.System:
            _domain = XenStore.XsDomain.System
        else:
            # We should look at the Domain id
            # to do later
            pass

        return _domain
