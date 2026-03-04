""" \author Tristan Israël """

from . import DiskState

class NotificationFactory:
    """ This class helps creating notifications

    All functions of this class are static.
    """

    @staticmethod
    def create_notification_disk_state(disk:str, state:DiskState) -> dict:
        """ Creates a notification for a disk's state """

        payload = {
            "disk": disk, 
            "state": state.value
        }

        return payload

    @staticmethod
    def create_notification_new_file(disk:str, filepath:str, source_fingerprint:str, dest_fingerprint:str) -> dict:
        """ Create a notification for a new file """

        payload = {            
            "disk": disk,
            "filepath": filepath,
            "source_fingerprint": source_fingerprint,
            "dest_fingerprint": dest_fingerprint
        }
        
        return payload
     
    @staticmethod
    def create_notification_error(disk:str, filepath:str, error:str) -> dict:
        """ Create a notification for an error """

        payload = {
            "disk": disk,
            "filepath": filepath,
            "error": error
        }

        return payload
    
    @staticmethod
    def create_notification_energy_state(battery) -> dict:
        """ Create a notification for the energy state """
        
        payload = {
            "battery_level": battery.percent,
            "plugged": 1 if battery.power_plugged else 0
        }

        return payload