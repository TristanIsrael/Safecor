""" \author Tristan Israël """

from . import Constants, Logger
import os
import hashlib
import subprocess
from pathlib import Path

class FileHelper():
    """ 
    This class defines helper function for querying the system about disks and files 

    Most of these functions are used on the sys-usb Domain by SysUsbController or on the Dom0
    by Dom0Controller.
    
    """

    @staticmethod
    def get_disks_list() -> list:
        """ This function returns the list of external disks connected to the system.

            The list of disks is obtained from the directories contained in :attr:`Constants.USB_MOUNT_POINT`,
            by checking whether they are mount points.

            This function does not return the list of files mounted.
        """

        disks = []
        mount_point = Constants.USB_MOUNT_POINT
        with os.scandir(mount_point) as folders:
            for folder in folders:
                if folder.is_dir():
                    if True: #os.path.ismount(folder.path):
                        #print(f"Disk found : {folder.name}")
                        disks.append(folder.name)

        return disks

    @staticmethod
    def get_files_list(disk:str, recursive:bool, from_dir:str="") -> list:
        """ 
        This function returns the complete directory tree of a mount point.

        The path used is built by concatenating the :attr:`Constants.USB_MOUNT_POINT` constant
        with the name passed as an argument.

        The list can be queried for external storages and files mounted.

        For each file or folder, a dictionary is created:
            { "type": "folder", "path": "/", "name": "dossier 1" },
            { "type": "file", "path": "/dossier 1", "name": "fichier 1", "size": 333344 },
            { "type": "file", "path": "/dossier 1/dossier 2", "name": "fichier 4", "size": 12 }
        """

        files_path = ""
        if disk == Constants.STR_REPOSITORY:
            files_path = Constants.DOM0_REPOSITORY_PATH
        else:
            #mount_point = Constants.USB_MOUNT_POINT
            mount_point = FileHelper.get_mount_point(disk)
            if mount_point is None:
                print("No mount point defined. Aborting.")
                return []
            
            files_path = mount_point

        #print(f"Getting files list for mount point {files_path}")
        
        fichiers = []
        FileHelper.get_folder_contents(files_path, fichiers, len(files_path), recursive, from_dir)

        return fichiers
       
    @staticmethod
    def get_folder_contents(path:str, contents_list:list, cutting:int = 0, recursive:bool = False, from_dir:str = ""):
        """ 
        Queries the contents of a folder 
        
        :param path: The path of the folder
        :param type: str
        :param contents_list: The list in which the new contents will be appended
        :param type: list
        :param cutting: If True the contents entry will be cut starting at this index
        :param type: bool
        :param recursive: If True the contents of each folder will by analyzed recursively
        :param type: bool
        :param from_dir: Specifies a start directory for the analysis. If not specified the analysis will start at the root of the disk.
        :param type: str
        """

        _real_filepath = f"{path}{from_dir}"

        #print("get_folder_contents : {} ({})".format(from_dir, _real_filepath))
        with os.scandir(_real_filepath) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                
                filepath = f"{path[cutting:]}{from_dir}"
                filename = entry.name
                if entry.is_file():
                    entryDict = {
                        "type": "file",
                        "path": "/" if filepath == "" else filepath,
                        "name": filename,
                        "size": entry.stat().st_size
                    }

                    contents_list.append(entryDict)
                elif entry.is_dir():
                    entryDict = {
                        "type": "folder",
                        "path": "/" if filepath == "" else filepath,
                        "name": filename
                    }

                    contents_list.append(entryDict)

                    if recursive:
                        FileHelper.get_folder_contents(entry.path, contents_list, cutting, recursive)


    #@staticmethod
    #def split_filepath(file_path:str) -> tuple[str, str]:
    #    spl = str.split(":")
    #
    #    if len(spl) == 1:
    #        return ("", spl[0])
    #    else:
    #        return (spl[0], spl[1])

    #@staticmethod
    #def make_filepath(disk_name:str, file_name:str) -> str:
    #    return f"{"" if disk_name is None else disk_name}:{file_name}"

    @staticmethod
    def calculate_fingerprint(filepath:str) -> str:
        """
        Calculates the fingerprint of a file.
        
        :param filepath: The full path of the file of which the fingerprint must be calculated.
        :type filepath: str
        :return: A sha-512 encoded fingerprint
        :rtype: str

        .. seealso::
            :func:`hashlib.file_digest`
        """
        try:
            with open(filepath, "rb") as f:
                h = hashlib.file_digest(f, Constants.FINGERPRINT_METHOD)
                return h.hexdigest()
        except Exception as e:
            print(f"An error occured while calculating the fingerprint of the file {filepath}")
            print(str(e))

        return ""
        
    @staticmethod
    def copy_file(source_disk:str, filepath:str, destination_disk:str, source_fingerprint:str) -> str:
        """
        Copies a file to another place.

        The destination directory must exist.

        The fingerprint of both files will compared at the end. The fingerprint is returned if they are identical.
        
        :param source_disk: The disk that contains the source file
        :type source_disk: str
        :param filepath: The path of the file on the source disk
        :type filepath: str
        :param destination_disk: The disk that will contain the copy
        :type destination_disk: str
        :param source_fingerprint: The fingerprint of the source file
        :type source_fingerprint: str
        :return: The fingerprint of the file if both fingerprints are equals, else an empty string
        :rtype: str
        """
        
        cmd = ['cp', f"{source_disk}{filepath}", f"{destination_disk}{filepath}"]
        
        try:
            subprocess.run(cmd, check= True, shell= False)
        except subprocess.CalledProcessError as e:
            Logger().debug(f"The file {filepath} could not be copied to {destination_disk}. Error: {str(e)}")
            return ""

        # Calculate the new file's fingerprint
        destination_file = f"{destination_disk}{filepath}"
        dest_fingerprint = FileHelper.calculate_fingerprint(destination_file)

        if source_fingerprint == dest_fingerprint:
            return dest_fingerprint
        else:
            Logger().debug(f"The file {filepath} has been copied to {destination_disk} but the fingerprints differ")
            return ""


    @staticmethod
    def copy_file_to_repository(source_disk:str, filepath:str, fingerprint:str):
        """
        Copies a file in the repository of the system.
        
        :param source_disk: The disk that contains the source file
        :type source_location: str
        :param filepath: The path of the sourc file
        :type filepath: str
        :param fingerprint: The fingerprint of the source file
        :type fingerprint: str
        """
        repository_path = Constants.DOMU_REPOSITORY_PATH
        FileHelper.copy_file(source_disk, filepath, repository_path, fingerprint)

    @staticmethod
    def create_file(filepath:str, size_ko:int):
        """
        Creates a new file on a disk

        If ``size_ko`` is different from 0, the file will be filled with random data.
        
        :param filepath: The path of the file to create
        :type filepath: str
        :param size_ko: The initial size of the new file
        :type size_ko: int
        """
        with open(filepath, 'wb') as fout:
            fout.write(os.urandom(size_ko*1024))

    @staticmethod
    def remove_file(filepath:str) -> bool:
        """
        Removes a file
        
        :param filepath: The path of the file to remove
        :type filepath: str
        :return: True if the file has been removed, else False
        :rtype: bool
        """
        try:
            os.remove(filepath)
            return True
        except Exception:
            return False
        
    @staticmethod
    def get_mount_point(disk:str) -> str|None:
        """ Returns the real mount point in the system 
        
        An external storage is mounted under /media/usb and a file is mounted in /media/loop. this function
        helps finding the correct mount point for a disk.

        :param disk: The name of the mount point
        """

        with open("/proc/mounts", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                mount_point = parts[1]
                if disk in mount_point:
                    return mount_point

        return None

    @staticmethod
    def is_archive_file(filename:str) -> bool:
        """ Verifies whether the file is (supposed to be) an archive file

        The verification is done with the file extension, not using the MIME type nor 
        controlling the MAGIC od the file. 
        """

        ext = Path(filename).suffix
        return ext in Constants.ARCHIVE_EXTENSIONS_HANDLED
