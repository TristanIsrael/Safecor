""" \author Tristan Israël """

import pyudev
from . import Logger, MqttClient, Topics, NotificationFactory, DiskState

class DiskMonitor():
    """ This class monitors a folder in order to detect the addition and removal of files and folders.    

    It works in polling mode because it needs to be compatible with XEN's 9pfs protocol which does not handle
    filesystem notifications.
    
    This class must be instanciated with the mount points directory that must be monitored (for instance ``/mnt``).

    Use case: Storage connection
    ============================

    When an external storage is connected, a new mount point is automatically created by the system (see ``udev`` or ``mdev``)
    in the mount points directory. For instance, if the storage is named ``NO NAME``, the mount point will be
    ``/mnt/NO NAME``.

    In such a case, the notification ``DISK_STATE`` will be sent.

    .. seealso::
        - :class:`Topics`
    
    Use case: Storage disconnection
    ===============================

    When an external storage is removed, the mount point is removed by the system in the mount points directory (``/mnt``).
    In such a case, the notification ``DISK_STATE`` will be sent.

    """    

    def __init__(self, folder:str, mqtt_client:MqttClient):
        Logger().setup("Disk monitor", mqtt_client)
        self.__disks = {}
        self.__folder = folder
        self.__mqtt_client = mqtt_client
        self.__is_started = False

    def device_event(self, action, device):
        if action == 'add':
            if device.device_type == "partition":
                if device.get('ID_FS_LABEL'):
                    mount_point = device.device_node
                    disk_name = device.get('ID_FS_LABEL')
                    Logger().info(f"USB Device connected. Partition detected: {mount_point} with name {disk_name}", "Disk monitor")
                    self.__disks[mount_point] = disk_name

                    payload = NotificationFactory.create_notification_disk_state(disk_name, DiskState.CONNECTED.value)
                    self.__mqtt_client.publish(Topics.DISK_STATE, payload)
        elif action == 'remove':
            if device.device_type == "partition":
                mount_point = device.device_node
                if mount_point in self.__disks:
                    Logger().info(f"USB Device disconnected on {device.device_node}", "Disk monitor")
                    disk_name = self.__disks.pop(mount_point)

                    payload = NotificationFactory.create_notification_disk_state(disk_name, DiskState.DISCONNECTED.value)
                    self.__mqtt_client.publish(Topics.DISK_STATE, payload)

    def start(self):
        Logger().debug(f"Starting disks monitoring on mount point {self.__folder}", "Disk monitor")

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block')

        self.__is_started = True

        for device in iter(monitor.poll, None):
            if not self.__is_started:
                break

            self.device_event(device.action, device)

    def stop(self):
        self.__is_started = False