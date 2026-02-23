""" \author Tristan Israël """

from . import Constants

class RequestFactory():
    """ The class MessageFactory generates notifications, commands and errors
    used in the communication between Domains.
    
    The emitter of the command is automatically added during the creation.

    **Reminder** Domains involved in the foundation are:
    - sys-usb which manages USB devices

    Notification are:

    - A DomU notifies Dom0 he has started (DomU to Dom0)
    - sys-usb notifies Dom0 that a USB storage is connected (DomU to Dom0)
    - sys-usb notifies Dom0 that a USB storage is disconnected (DomU to Dom0)

    Commands are:

    - Logging

      - A Domain adds an entry in the log (DomU to Dom0)
      - Dom0 records the log on a USB storage (DomU to Dom0)

    - System

      - A DomU asks for the debug status (DomU to Dom0)
      - A DomU asks for to reboot of the system (DomU to Dom0)
      - A DomU asks for to shut the system down (DomU to Dom0)
      - A DomU asks for the reset of another DomU (DomU to Dom0)
      - A DomU asks for the batery level (DomU to Dom0)
      - A DomU asks for the charging state (DomU to Dom0)

    - Files

      - A DomU asks for the list of storages (DomU to Dom0 to sys-usb)
      - A DomU asks for the creation of a secure archive on a USB storage (DomU to Dom0 to sys-usb)
      - A DomU asks for adding a file to a secure archive (DomU to Dom0 to sys-usb)
      - A DomU asks for the copy of a file (DomU to Dom0 to sys-usb)    
      
    - Notifications
    
      - To do
    
    """   

    @staticmethod
    def create_request_files_list(disk: str, recursive: bool = False, from_dir: str = "") -> dict:
        """ Creates a request to receive the files list of a storage """

        return { 
            "disk": disk,
            "recursive": recursive,
            "from_dir": from_dir
            }
    
    @staticmethod
    def create_request_read_file(disk : str, filepath : str) -> dict:
        """ Creates a request to read a file's content """

        return {
            "disk": disk,
            "filepath": filepath
        }        
    
    @staticmethod
    def create_request_copy_file(source_disk:str, filepath:str, destination_disk:str) -> dict :
        """ Create a request to copy a file from a storage to another, including the repository.
            
            Example :
            
            ::
                
                { filepath: "External storage:/a path/a filename", disk_destination: "Another storage" }
        """

        return {
            "disk": source_disk,
            "filepath": filepath,
            "destination": destination_disk
        }        
    
    @staticmethod
    def create_request_delete_file(filepath: str, disk: str = Constants.STR_REPOSITORY) -> dict:
        """ Create a request to delete a file from a storage 
        
            :param filepath: The filepath of the file to delete
            :type a: str
            :param disk: The storage name - Default value is the local repository
            :type disk: str
        """

        return {
            "filepath": filepath,
            "disk": disk
        }
    
    @staticmethod
    def create_request_start_benchmark(id_benchmark: str):
        """ Create a request to start the benchmark """

        return {
            "module": id_benchmark
        }        

    @staticmethod 
    def create_request_get_file_fingerprint(filepath:str, disk:str) -> dict:
        """ Create a request to get a file's fingerprint """

        return {
            "filepath": filepath,
            "disk": disk
        }        
    
    @staticmethod
    def create_request_create_file(filepath:str, disk:str, contents:bytes, compressed:bool=False) -> dict:
        """ Create a request to create a new file on a storage 
        
            :param filepath: The filepath of file to create
            :type filepath: str
            :param disk: The storage on which the file should be created
            :type disk: str
            :param contents: The data to write in the file as a byte array
            :type contents: bytes
            :param compressed: Indicates whether the data should be compressed - Default is False
            :type compressed: bool
        """

        return {
            "filepath": filepath,
            "disk": disk,
            "data": contents.decode("utf-8"),
            "compressed": compressed
        }    

    @staticmethod
    def create_request_restart_domain(domain_name:str):
        """ Create a request to restart a Domain """

        return {
            "domain_name": domain_name
        }
    
    @staticmethod
    def create_request_ping(ping_id, source_name, data, datetime):
        """ Create a request to ping a Domain 
        
            When a Domain is pinged it should answer automatically with a ping response.
        """

        return {
            "id": ping_id,
            "source": source_name,
            "data": data,
            "sent_at": datetime
        }
        
    @staticmethod
    def create_request_set_log_level(log_level):
        """ Create a request to set the log level 
        
        Log levels are defined in the default logging module.
        """

        return {
            "level": log_level
        }
    
    @staticmethod
    def create_request_save_log(disk:str, filename:str):
        """ Create a request to save the log file """

        return {
            "disk": disk,
            "filename": filename
        }
    
    @staticmethod
    def create_request_mount_file(disk:str, filepath:str):
        """ Create a request to mount a file """

        return {
            "disk": disk,
            "filepath": filepath
        }
    
    @staticmethod
    def create_request_unmount(disk:str):
        """ Create a request to unmount a disk """

        return {
            "disk": disk
        }