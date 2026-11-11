""" Mock sys-usb controller

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import base64
import os
import platform
import shutil
import subprocess
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Optional

from safecor import (
    ConnectionType,
    Constants,
    DiskState,
    FileHelper,
    MqttClient,
    MqttHelper,
    NotificationFactory,
    ResponseFactory,
    Topics,
)

from ..events import EventBus


class MockSysUsbController:
    def __init__(
        self,
        sync_lock: Event,
        client_id_suffix: str = "",
        event_bus: Optional[EventBus] = None,
    ):
        self.__thread_pool = ThreadPoolExecutor(max_workers=1)
        self.__sync_lock = sync_lock
        self.__mqtt_client = None
        self.__client_id_suffix = client_id_suffix
        self.__event_bus = event_bus
        self.__destination_disk_path = ""
        self.__known_disk_ids: set = set()

    # --- event bus helpers ---------------------------------------------------
    def __emit(self, stream: str, text: str, payload: Optional[dict] = None):
        if self.__event_bus is not None:
            self.__event_bus.publish(stream, "SysUsb", text, payload)

    def __publish(self, topic: str, payload: dict):
        self.__emit("mqtt_events", f"SysUsb -> {topic}", payload)
        self.__mqtt_client.publish(topic, payload)

    def __log(self, message: str):
        self.__emit("platform_log", message)
        print(f"[SYS-USB] {message}")

    def start(
        self, source_disks_list: dict, storage_path: str
    ):
        """Start the MQTT client and expose the given local directories as disks.

        :param source_disks_list: mapping of disk id -> root directory (source of files).
        :param storage_path: local directory that emulates the repository.
        """
        self.__source_disks_list = source_disks_list
        self.__storage_path = storage_path

        self.__mqtt_client = MqttClient(
            f"sys-usb{self.__client_id_suffix}", ConnectionType.TCP_DEBUG, "localhost"
        )
        self.__mqtt_client.on_connected = self.__on_mqtt_connected
        self.__mqtt_client.on_message = self.__on_mqtt_message
        self.__mqtt_client.start()

    def stop(self):
        """Stop the underlying MQTT client and thread pool."""
        try:
            if self.__mqtt_client is not None:
                self.__mqtt_client.stop()
        except Exception:
            pass
        self.__thread_pool.shutdown(wait=False)

    def attach_disk(self, disk_id: str, root_path: str):
        """Hot-plug a disk: expose ``root_path`` as ``disk_id`` and announce it.

        The last attached disk is considered the copy destination (target).
        Re-attaching a previously known disk does not change the destination.

        Publishes a ``DISK_STATE`` ``connected`` notification, mirroring what the
        real sys-usb controller does when a USB disk is inserted.
        """
        if self.__mqtt_client is None:
            raise RuntimeError("MockSysUsbController.start() must be called first")
        os.makedirs(root_path, exist_ok=True)
        is_new_disk = disk_id not in self.__known_disk_ids
        self.__known_disk_ids.add(disk_id)
        self.__source_disks_list[disk_id] = root_path
        if is_new_disk:
            self.__destination_disk_path = root_path
        self.__publish(
            Topics.DISK_STATE,
            NotificationFactory.create_notification_disk_state(
                disk_id, DiskState.CONNECTED
            ),
        )

    def detach_disk(self, disk_id: str):
        """Hot-unplug a disk: remove ``disk_id`` and announce it.

        Publishes a ``DISK_STATE`` ``disconnected`` notification.
        """
        if self.__mqtt_client is None:
            raise RuntimeError("MockSysUsbController.start() must be called first")
        if self.__source_disks_list.pop(disk_id, None) is None:
            self.__log(f"ERROR: disk {disk_id} is not attached")
            return
        self.__publish(
            Topics.DISK_STATE,
            NotificationFactory.create_notification_disk_state(
                disk_id, DiskState.DISCONNECTED
            ),
        )

    def __on_mqtt_connected(self):
        self.__log("MQTT client connected")
        self.__mqtt_client.subscribe(f"{Topics.LIST_DISKS}/request")
        self.__mqtt_client.subscribe(f"{Topics.LIST_FILES}/request")
        self.__mqtt_client.subscribe(f"{Topics.READ_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.COPY_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.CREATE_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.MOUNT_FILE}/request")
        self.__mqtt_client.subscribe(f"{Topics.UNMOUNT}/request")
        self.__mqtt_client.subscribe(f"{Topics.DISCOVER_COMPONENTS}/request")

        # Finally we announce our components
        self.__handle_discover_components()

        self.__sync_lock.set()

    def __on_mqtt_message(self, topic: str, payload: dict):
        self.__emit("mqtt_events", f"SysUsb <- {topic}", payload)
        self.__thread_pool.submit(self.__message_worker, topic, payload)

    def __message_worker(self, topic: str, payload: dict):
        if topic == f"{Topics.LIST_DISKS}/request":
            response = ResponseFactory.create_response_disks_list(
                list(self.__source_disks_list.keys())
            )
            self.__publish(f"{Topics.LIST_DISKS}/response", response)
        elif topic == f"{Topics.LIST_FILES}/request":
            self.__handle_list_files(payload)
        elif topic == f"{Topics.READ_FILE}/request":
            if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
                self.__log("Missing arguments")
                return

            disk = payload.get("disk", "")
            filepath = payload.get("filepath", "")

            # Verify and create the local storage if needed
            if not os.path.exists(self.__storage_path):
                os.makedirs(self.__storage_path)

            if disk not in self.__source_disks_list:
                self.__log(f"ERROR: The disk {disk} does not exist.")
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

                notif = NotificationFactory.create_notification_new_file(
                    Constants.STR_REPOSITORY,
                    filepath,
                    source_fingerprint,
                    dest_fingerprint,
                )
                self.__publish(Topics.NEW_FILE, notif)
            except Exception as e:
                self.__log(f"Error during copy: {str(e)}")
                notif = NotificationFactory.create_notification_error(
                    disk, filepath, "The file could not be copied"
                )
                self.__publish(Topics.ERROR, notif)
                return
        elif topic == f"{Topics.DISCOVER_COMPONENTS}/request":
            self.__handle_discover_components()
        elif topic == f"{Topics.COPY_FILE}/request":
            if not MqttHelper.check_payload(
                payload, ["disk", "filepath", "destination"]
            ):
                self.__log(f"Missing arguments for topic {topic}")
                return

            disk = payload.get("disk", "")
            filepath = payload.get("filepath", "")
            destination = payload.get("destination", "")

            if disk not in self.__source_disks_list:
                self.__log(f"ERROR: The disk {disk} does not exist.")
                return

            if destination not in self.__source_disks_list:
                self.__log(
                    f"ERROR: The destination disk {destination} is not connected."
                )
                response = ResponseFactory.create_response_copy_file(
                    filepath, disk, False, ""
                )
                self.__publish(f"{Topics.COPY_FILE}/response", response)
                return

            root_path = self.__source_disks_list[disk]
            source_path = f"{root_path}{filepath}"
            dest_filepath = f"{self.__destination_disk_path}{filepath}"
            dest_path = os.path.dirname(dest_filepath)

            if not os.path.exists(dest_path):
                os.makedirs(dest_path)

            try:
                shutil.copy(source_path, dest_path)

                source_fingerprint = FileHelper.calculate_fingerprint(source_path)
                dest_fingerprint = FileHelper.calculate_fingerprint(dest_filepath)

                if source_fingerprint != dest_fingerprint:
                    self.__log("ERROR: fingerprints are not equal")

                response = ResponseFactory.create_response_copy_file(
                    filepath,
                    disk,
                    source_fingerprint == dest_fingerprint,
                    source_fingerprint,
                )
                self.__publish(f"{Topics.COPY_FILE}/response", response)
            except Exception:
                notif = NotificationFactory.create_notification_error(
                    disk, filepath, "The file could not be copied"
                )
                self.__publish(Topics.ERROR, notif)
        elif topic == f"{Topics.CREATE_FILE}/request":
            self.__handle_create_file(payload)
        elif topic == f"{Topics.MOUNT_FILE}/request":
            self.__handle_mount_file(payload)
        elif topic == f"{Topics.UNMOUNT}/request":
            self.__handle_unmount(payload)

    def __handle_discover_components(self):
        response = {
            "components": [
                {
                    "id": Constants.SAFECOR_DISK_CONTROLLER,
                    "label": "Mock disk controller",
                    "type": "core",
                    "state": "ready",
                },
                {
                    "id": Constants.SAFECOR_INPUT_CONTROLLER,
                    "label": "Mock input controller",
                    "type": "core",
                    "state": "ready",
                },
                {
                    "id": Constants.SAFECOR_SYSTEM_CONTROLLER,
                    "label": "Mock Dom0 controller",
                    "type": "core",
                    "state": "ready",
                },
            ]
        }
        self.__publish(f"{Topics.DISCOVER_COMPONENTS}/response", response)

    def __handle_list_files(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["disk", "recursive", "from_dir"]):
            self.__log("Missing arguments")
            return

        disk = payload.get("disk")
        recursive = payload.get("recursive", False)
        from_dir = payload.get("from_dir", "")
        name_filters = payload.get("name_filters", None)

        if disk not in self.__source_disks_list:
            self.__log(f"ERROR: The disk {disk} does not exist.")
            return

        root_path = self.__source_disks_list[disk]
        if not os.path.exists(root_path):
            self.__log(f"The folder {root_path} does not exist")
            return

        files = list()
        FileHelper.get_folder_contents(
            root_path, files, len(root_path), recursive, from_dir, name_filters
        )

        response = ResponseFactory.create_response_list_files(disk, files)
        self.__publish(f"{Topics.LIST_FILES}/response", response)

    def __handle_create_file(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath", "data"]):
            self.__log("Missing argument in the create_file command")
            return

        disk = payload.get("disk", "")
        filepath = payload.get("filepath", "")
        base64_data = payload.get("data", "")

        if disk == Constants.STR_REPOSITORY:
            # Ignored
            return

        if disk not in self.__source_disks_list:
            self.__log(f"ERROR: The disk {disk} is not connected.")
            response = ResponseFactory.create_response_create_file(
                filepath, disk, "", False
            )
            self.__publish(f"{Topics.CREATE_FILE}/response", response)
            return

        decoded = base64.b64decode(base64_data)

        # Check if data were compressed, and uncompress if needed
        compressed = payload.get("compressed", False)
        if compressed:
            data = zlib.decompress(decoded)
        else:
            data = decoded

        complete_filepath = f"{self.__destination_disk_path}/{filepath}"

        self.__log(
            f"Create a file {filepath} of size {len(data)} octets on disk {disk}"
        )

        try:
            with open(complete_filepath, "wb") as f:
                f.write(data)
        except Exception as e:
            self.__log(f"An error occured while writing to file {complete_filepath}")
            self.__log(str(e))

            response = ResponseFactory.create_response_create_file(
                filepath, disk, "", False
            )
            self.__publish(f"{Topics.CREATE_FILE}/response", response)
            return

        # On envoie la notification de succès
        fingerprint = FileHelper.calculate_fingerprint(complete_filepath)
        response = ResponseFactory.create_response_create_file(
            complete_filepath, disk, fingerprint, True
        )
        self.__publish(f"{Topics.CREATE_FILE}/response", response)

    def __handle_mount_file(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            self.__log("Missing argument in the mount_file command")
            return

        disk = payload["disk"]
        filepath = payload["filepath"]

        root_path = self.__source_disks_list[disk]
        if not os.path.exists(root_path):
            self.__log(f"The folder {root_path} does not exist")
            return

        archive_filepath = f"{root_path}/{filepath}"
        archive_filename = Path(filepath).name
        mount_point = f"/tmp/{archive_filename}"

        try:
            if not os.path.exists(mount_point):
                os.mkdir(mount_point)

            if platform.system() == "Darwin":
                subprocess.run(
                    ["hdiutil", "attach", "-mountpoint", mount_point, archive_filepath],
                    check=False,
                )
            elif platform.system() == "Linux":
                subprocess.run(
                    ["mount", "-o", "loop", archive_filepath, mount_point], check=False
                )

            # Add it to the source disks list
            self.__source_disks_list[archive_filename] = mount_point

            notif = NotificationFactory.create_notification_disk_state(
                archive_filename, DiskState.MOUNTED
            )
            self.__publish(Topics.DISK_STATE, notif)
        except Exception as e:
            self.__log(f"ERROR when mounting file {archive_filepath}: {str(e)}")

    def __handle_unmount(self, payload: dict):
        if not MqttHelper.check_payload(payload, ["disk"]):
            self.__log("Missing argument in the unmount command")
            return

        disk = payload["disk"]

        if disk not in self.__source_disks_list:
            self.__log(f"Error: disk {disk} is not mounted")
            return

        mount_point = self.__source_disks_list[disk]

        try:
            if platform.system() == "Darwin":
                subprocess.run(["hdiutil", "detach", mount_point])
            elif platform.system() == "Linux":
                subprocess.run(["umount", mount_point])

            # Remove from the source disks list
            self.__source_disks_list.pop(disk, None)
            notif = NotificationFactory.create_notification_disk_state(
                disk, DiskState.UNMOUNTED
            )
            self.__publish(Topics.DISK_STATE, notif)
        except Exception as e:
            self.__log(f"ERROR when unmounting {disk}: {str(e)}")
