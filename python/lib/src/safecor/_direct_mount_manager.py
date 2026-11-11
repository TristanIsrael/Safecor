""" Direct USB mount manager.

Manages the direct USB mount from sys-usb via vchan+sshfs in a DomU.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import signal
import subprocess
import sys
import time

from . import Constants, Logger, MqttFactory, System, Topics

VCHAN_SFTP_SCRIPT_PATH = "/usr/local/bin/vchan-sftp"
DOMID_WAIT_TIMEOUT = 60
DOMID_POLL_INTERVAL = 2


class DirectMountManager:
    """ Manages the direct USB mount from sys-usb via vchan+sshfs.

    This class runs in its own process (started by openrc). It handles the
    complete flow: querying the topology, discovering the sys-usb domid,
    generating the vchan client script, and mounting via sshfs.

    Product applications should use `System.is_usb_mountpoint_ready()` and
    `System.on_usb_mountpoint_ready(callback)` to check or wait for the
    mount to become available, rather than interacting with this class directly.

    .. seealso::
        :class:`System` - For mount point status queries
    """

    __mounted = False
    __sshfs_process = None
    __mount_mode = "rw"

    def start(self) -> bool:
        """ Initiates the direct mount flow.

        Steps:
            1. Query my_config to check if this domain has direct_mount.
            2. Discover the sys-usb domid from xenstore (with retry).
            3. Generate the vchan-sftp client script.
            4. Mount via sshfs.

        Returns:
            True if the mount was successful, False otherwise.
        """
        # Step 1: Check if this domain has direct_mount enabled
        mount_mode = self.__query_direct_mount_config()
        if mount_mode is None:
            Logger().info(
                "DirectMountManager: this domain does not have direct_mount enabled"
            )
            return False

        self.__mount_mode = mount_mode
        Logger().info(f"DirectMountManager: direct_mount enabled (mode={mount_mode})")

        # Step 2: Get sys-usb domid
        domid = self.__wait_for_domid("sys-usb")
        if domid is None:
            Logger().error("DirectMountManager: could not find sys-usb domid")
            return False

        Logger().info(f"DirectMountManager: sys-usb domid is {domid}")

        # Step 3: Generate vchan-sftp script
        if not self.__generate_vchan_script(domid):
            Logger().error("DirectMountManager: failed to generate vchan-sftp script")
            return False

        # Step 4: Mount
        if not self.__mount():
            Logger().error("DirectMountManager: failed to mount")
            return False

        self.__mounted = True
        Logger().info(f"DirectMountManager: mounted at {Constants.USB_MOUNT_POINT}")
        return True

    def stop(self) -> None:
        """ Unmounts and cleans up the direct mount. """
        if self.__sshfs_process is not None:
            try:
                self.__sshfs_process.terminate()
                self.__sshfs_process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                self.__sshfs_process.kill()
            self.__sshfs_process = None

        self.__unmount()
        self.__mounted = False
        Logger().info("DirectMountManager: unmounted")

    def is_mounted(self) -> bool:
        """ Returns True if the direct mount is active. """
        return self.__mounted

    def get_mount_point(self) -> str:
        """ Returns the mount point path. """
        return Constants.USB_MOUNT_POINT

    def run(self) -> None:
        """ Entry point for running as a standalone process.

        Blocks until a termination signal is received.
        """
        signal.signal(signal.SIGTERM, self.__handle_signal)
        signal.signal(signal.SIGINT, self.__handle_signal)

        if self.start():
            # Block until terminated
            while self.__mounted:
                time.sleep(1)
        else:
            sys.exit(1)

    def __handle_signal(self, signum, frame):
        """ Handle SIGTERM/SIGINT: stop the mount and exit. """
        Logger().info("DirectMountManager: received termination signal")
        self.stop()
        sys.exit(0)

    def __query_direct_mount_config(self):
        """ Query my_config via MQTT to check if this domain has direct_mount.

        Returns:
            The mount mode ("ro" or "rw"), or None if not enabled.
        """
        try:
            domain_name = System.domain_name()
            api_helper = MqttFactory().get_api_helper()
            response = api_helper.send_request(Topics.MY_CONFIG, {})
            if response:
                for d in response.get("domains", []):
                    if d.get("name") == domain_name:
                        dm = d.get("direct_mount")
                        if dm:
                            return dm.get("mode", "rw")
        except Exception as e:
            Logger().error(f"DirectMountManager: error querying my_config: {e}")
        return None

    def __wait_for_domid(self, domain_name: str):
        """ Poll xenstore for the domain's domid with a timeout.

        Returns:
            The domid as int, or None if not found within timeout.
        """
        deadline = time.time() + DOMID_WAIT_TIMEOUT
        while time.time() < deadline:
            domid = System().get_domain_domid(domain_name)
            if domid is not None:
                return domid
            time.sleep(DOMID_POLL_INTERVAL)
        return None

    def __generate_vchan_script(self, domid: int) -> bool:
        """ Generate the vchan-socket-proxy client script. """
        try:
            os.makedirs(os.path.dirname(VCHAN_SFTP_SCRIPT_PATH), exist_ok=True)
            content = (
                f"#!/bin/sh\n"
                f"exec vchan-socket-proxy -m client {domid} "
                f"/local/domain/{domid}/data/vchan/sftp -\n"
            )
            with open(VCHAN_SFTP_SCRIPT_PATH, "w") as f:
                f.write(content)
            os.chmod(VCHAN_SFTP_SCRIPT_PATH, 0o755)
            return True
        except OSError as e:
            Logger().error(f"DirectMountManager: cannot write vchan script: {e}")
            return False

    def __mount(self) -> bool:
        """ Mount the USB folder via sshfs over vchan. """
        mount_point = Constants.USB_MOUNT_POINT
        os.makedirs(mount_point, exist_ok=True)

        opts = (
            f"ssh_command={VCHAN_SFTP_SCRIPT_PATH},"
            f"noexec,nosuid,nodev,default_permissions,max_read=131072"
        )
        if self.__mount_mode == "ro":
            opts += ",ro"

        try:
            self.__sshfs_process = subprocess.Popen(
                ["sshfs", "-f", "-o", opts, "none:/", mount_point],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Give it a moment to establish
            time.sleep(2)
            if self.__sshfs_process.poll() is None:
                return True
            else:
                Logger().error(
                    f"DirectMountManager: sshfs exited with code "
                    f"{self.__sshfs_process.returncode}"
                )
                return False
        except (OSError, FileNotFoundError) as e:
            Logger().error(f"DirectMountManager: sshfs failed to start: {e}")
            return False

    def __unmount(self) -> None:
        """ Unmount the sshfs mount point. """
        mount_point = Constants.USB_MOUNT_POINT
        try:
            subprocess.run(["fusermount", "-u", mount_point], timeout=10)
        except (subprocess.SubprocessError, OSError):
            try:
                subprocess.run(["umount", mount_point], timeout=10)
            except (subprocess.SubprocessError, OSError):
                pass
