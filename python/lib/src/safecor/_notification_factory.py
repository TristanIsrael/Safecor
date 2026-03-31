""" \author Tristan Israël """

from . import DiskState

class NotificationFactory:
    """ This class helps creating notifications

    All functions of this class are static.
    """

    @staticmethod
    def create_notification_disk_state(disk:str, state:DiskState) -> dict:
        """ Creates a notification for a disk's state """

        return {
            "disk": disk, 
            "state": state.value
        }

    @staticmethod
    def create_notification_new_file(disk:str, filepath:str, source_fingerprint:str, dest_fingerprint:str) -> dict:
        """ Create a notification for a new file """

        return {
            "disk": disk,
            "filepath": filepath,
            "source_fingerprint": source_fingerprint,
            "dest_fingerprint": dest_fingerprint
        }
     
    @staticmethod
    def create_notification_error(disk:str, filepath:str, error:str) -> dict:
        """ Create a notification for an error """

        return {
            "disk": disk,
            "filepath": filepath,
            "error": error
        }
    
    @staticmethod
    def create_notification_energy_state(battery) -> dict:
        """ Create a notification for the energy state """
        
        return {
            "battery_level": round(battery.percent, 2),
            "plugged": 1 if battery.power_plugged else 0
        }
    
    @staticmethod
    def create_notification_deleted_file(disk:str, filepath:str) -> dict:
        """ Create a notification for a file deletion """

        return {
            "disk": disk,
            "filepath": filepath
        }
    
    @staticmethod
    def create_notification_setting_changed(key:str, value) -> dict:
        """ Create a notification for a setting of which value has changed """

        return {
            "key": key,
            "value": value
        } 
    