""" \author Tristan Israël """

import os, shutil
from safecor import MqttClient, ConnectionType, Topics, ResponseFactory, FileHelper, MqttHelper, NotificationFactory, Constants, DiskState
from concurrent.futures import ThreadPoolExecutor
import base64, zlib
import platform
import subprocess
from pathlib import Path
from threading import Event

class MockSysUsbController():

    def __init__(self, sync_lock:Event):
        self.__thread_pool = ThreadPoolExecutor(max_workers=1)
        self.__sync_lock = sync_lock


    def start(self, source_disks_list:dict, storage_path:str, destination_disk_path:str):
        self.__source_disks_list = source_disks_list
        self.__storage_path = storage_path
        self.__destination_disk_path = destination_disk_path

        self.__mqtt_client = MqttClient("sys-usb", ConnectionType.TCP_DEBUG, "localhost")
        self.__mqtt_client.on_connected = self.__on_mqtt_connected
        self.__mqtt_client.on_message = self.__on_mqtt_message
        self.__mqtt_client.start()


    def __on_mqtt_connected(self):
        self.__debug("MQTT client connected")
        self.__mqtt_client.subscribe(f"{Topics.SYSTEM}/+/+/request")
        self.__mqtt_client.subscribe(f"{Topics.DISCOVER}/+/request")

        # Finally we announce our components
        self.__handle_discover_components()

        self.__sync_lock.set()


    def __on_mqtt_message(self, topic:str, payload:dict):
        #self.__debug("Message received on topic {}".format(topic))

        self.__thread_pool.submit(self.__message_worker, topic, payload)

    def __message_worker(self, topic:str, payload:dict):
        if topic == f"{Topics.LIST_DISKS}/request":
            response = ResponseFactory.create_response_disks_list(list(self.__source_disks_list.keys()))
            self.__mqtt_client.publish(f"{Topics.LIST_DISKS}/response", response)
        elif topic == f"{Topics.LIST_FILES}/request".format():
            self.__handle_list_files(payload)
        elif topic == f"{Topics.READ_FILE}/request".format():
            if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
                self.__debug("Missing arguments")
                return

            disk = payload.get("disk", "")
            filepath = payload.get("filepath", "")

            # Verify and create the local storage if needed
            if not os.path.exists(self.__storage_path):
                # Créer le dossier
                os.makedirs(self.__storage_path)

            if disk not in self.__source_disks_list:
                print(f"ERROR: The disk {disk} does not exist.")
                return
            
            root_path = self.__source_disks_list[disk]
            source_path = f"{root_path}/{filepath}"
            dest_filepath = f"{self.__storage_path}/{filepath}"
            dest_path = os.path.dirname(dest_filepath)

            # Verify and create paths if needed
            if not os.path.exists(dest_path):
                os.makedirs(dest_path)

            try:
                shutil.copy(source_path, dest_path)

                source_fingerprint = FileHelper.calculate_fingerprint(source_path)
                dest_fingerprint = FileHelper.calculate_fingerprint(dest_filepath)

                notif = NotificationFactory.create_notification_new_file(Constants.STR_REPOSITORY, filepath, source_fingerprint, dest_fingerprint)
                self.__mqtt_client.publish(Topics.NEW_FILE, notif)
            except Exception as e:
                self.__debug(f"Error during copy: {str(e)}")
                notif = NotificationFactory.create_notification_error(disk, filepath, "The file could not be copied")
                self.__mqtt_client.publish(Topics.ERROR, notif)
                return            
        elif topic == f"{Topics.DISCOVER_COMPONENTS}/request":
            self.__handle_discover_components()
        elif topic == f"{Topics.COPY_FILE}/request":
            if not MqttHelper.check_payload(payload, ["disk", "filepath", "destination"]):
                self.__debug(f"Missing arguments for topic {topic}")
                return 
            
            disk = payload.get("disk", "")
            filepath = payload.get("filepath", "")

            if disk not in self.__source_disks_list:
                print(f"ERROR: The disk {disk} does not exist.")
                return
            
            root_path = self.__source_disks_list[disk]
            source_path = f"{root_path}/{root_path}"
            dest_filepath = f"{Topics.COPY_FILE}/{filepath}"
            dest_path = os.path.dirname(dest_filepath)


            if not os.path.exists(dest_path):
                os.makedirs(dest_path)

            try:
                shutil.copy(source_path, dest_path)

                source_fingerprint = FileHelper.calculate_fingerprint(source_path)
                dest_fingerprint = FileHelper.calculate_fingerprint(dest_filepath)

                if source_fingerprint != dest_fingerprint:
                    self.__debug("ERROR: fingerprints are not equal")

                response = ResponseFactory.create_response_copy_file(filepath, disk, source_fingerprint == dest_fingerprint, source_fingerprint)
                self.__mqtt_client.publish(f"{Topics.COPY_FILE}/response", response)
            except Exception: 
                notif = NotificationFactory.create_notification_error(disk, filepath, "The file could not be copied")
                self.__mqtt_client.publish(Topics.ERROR, notif)

            source_fingerprint = FileHelper.calculate_fingerprint(source_path)
        elif topic == f"{Topics.CREATE_FILE}/request":
            self.__handle_create_file(payload)
        elif topic == f"{Topics.MOUNT_FILE}/request":
            self.__handle_mount_file(payload)
        elif topic == f"{Topics.UNMOUNT}/request":
            self.__handle_unmount(payload)

    def __handle_discover_components(self):
        response = {
            "components": [
                { "id": Constants.SAFECOR_DISK_CONTROLLER, "label": "System disk controller", "type": "core", "state": "ready" },
                { "id": Constants.SAFECOR_INPUT_CONTROLLER, "label": "Input controller", "type": "core", "state": "ready" },
                { "id": Constants.IO_BENCHMARK, "label": "System I/O benchmark", "type": "core", "state": "ready" }
            ]
        }

        self.__mqtt_client.publish(f"{Topics.DISCOVER_COMPONENTS}/response", response)

    def __handle_list_files(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["disk", "recursive", "from_dir"]):
            self.__debug("Missing arguments")
            return

        disk = payload.get("disk")
        recursive = payload.get("recursive", False)
        from_dir = payload.get("from_dir", "")

        if disk not in self.__source_disks_list:
            print(f"ERROR: The disk {disk} does not exist.")
            return
        
        root_path = self.__source_disks_list[disk]
        if not os.path.exists(root_path):
            self.__debug(f"The folder {root_path} does not exist")
            return

        files = list()
        FileHelper.get_folder_contents(root_path, files, len(root_path), recursive, from_dir)

        response = ResponseFactory.create_response_list_files(disk, files)
        self.__mqtt_client.publish(f"{Topics.LIST_FILES}/response", response)

    def __handle_create_file(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath", "data"]):
            self.__debug("Missing argument in the create_file command")
            return
        
        disk = payload.get("disk", "")
        filepath = payload.get("filepath", "")
        base64_data = payload.get("data", "")


        if disk == Constants.STR_REPOSITORY:
            # Ignored
            return

        decoded = base64.b64decode(base64_data)

        # Check if data were compressed, and uncompress if needed
        compressed = payload.get("compressed", False)
        if compressed:
            data = zlib.decompress(decoded)
        else:
            data = decoded

        complete_filepath = f"{self.__destination_disk_path}/{filepath}"
        
        self.__debug(f"Create a file {filepath} of size {data} octets on disk {disk}")

        try:
            with open(complete_filepath, 'wb') as f:
                f.write(data)
            f.close()            
        except Exception as e:
            self.__debug(f"An error occured while writing to file {complete_filepath}")
            self.__debug(str(e))
            
            response = ResponseFactory.create_response_create_file(filepath, disk, "", False)
            self.__mqtt_client.publish(f"{Topics.CREATE_FILE}/response".format(), response)
            return

        # On envoie la notification de succès
        fingerprint = FileHelper.calculate_fingerprint(complete_filepath)
        response = ResponseFactory.create_response_create_file(complete_filepath, disk, fingerprint, True)
        self.__mqtt_client.publish(f"{Topics.CREATE_FILE}/response", response)


    def __handle_mount_file(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            self.__debug("Missing argument in the mount_file command")
            return

        disk = payload["disk"]
        filepath = payload["filepath"]

        root_path = self.__source_disks_list[disk]
        if not os.path.exists(root_path):
            self.__debug(f"The folder {root_path} does not exist")
            return
        
        archive_filepath = f"{root_path}/{filepath}"
        archive_filename = Path(filepath).name
        mount_point = f"/tmp/{archive_filename}"

        try :
            if not os.path.exists(mount_point):
                os.mkdir(mount_point)

            if platform.system() == 'Darwin':
                subprocess.run(["hdiutil", "attach", "-mountpoint", mount_point, archive_filepath], check=False)
            elif platform.system() == "Linux":
                subprocess.run(["mount", "-o", "loop", archive_filepath, mount_point], check=False)

            # Add it to the source disks list
            self.__source_disks_list[archive_filename] = mount_point

            notif = NotificationFactory.create_notification_disk_state(archive_filename, DiskState.MOUNTED.value)
            self.__mqtt_client.publish(Topics.DISK_STATE, notif)
        except Exception as e:
            print(f"ERROR when mounting file {archive_filepath}: {str(e)}")

    def __handle_unmount(self, payload:dict):
        if not MqttHelper.check_payload(payload, ["disk"]):
            self.__debug("Missing argument in the mount_file command")
            return

        disk = payload["disk"]

        if disk not in self.__source_disks_list:
            print(f"Error: disk {disk} is not mounted")

        mount_point = self.__source_disks_list[disk]

        try:
            if platform.system() == 'Darwin':
                subprocess.run(["hdiutil", "detach", mount_point])
            elif platform.system() == "Linux":
                subprocess.run(["umount", mount_point])

            # Remove from the source disks list
            self.__source_disks_list.pop(disk, None)
            notif = NotificationFactory.create_notification_disk_state(disk, DiskState.UNMOUNTED.value)
            self.__mqtt_client.publish(Topics.DISK_STATE, notif)
        except Exception as e:
            print(f"ERROR when unmounting {disk}: {str(e)}")

    def __connect_destination(self):        
        notif = NotificationFactory.create_notification_disk_state("TARGET", DiskState.CONNECTED.value)
        self.__mqtt_client.publish(Topics.DISK_STATE, notif)

    def __debug(self, message:str):
        print(f"[SYS-USB] {message}")
