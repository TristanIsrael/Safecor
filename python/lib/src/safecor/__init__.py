__author__ = "Tristan Israël (tristan.israel@alefbet.net)"
__version__ = '1.4.0'

import logging
from logging import NullHandler

from ._topology import Topology, Domain, Screen, DomainType
from ._singleton import SingletonMeta
from ._constants import Constants, InputType, BenchmarkId, ComponentState, DiskState, Settings
from ._syslogger import SysLogger

try:
    from ._xcb_controller import XcbController
except ImportError as e:
    print("The class XcbController won't be available due to missing dependency")
    print(str(e))

try:
    from ._xenstore import XenStore, XsDomain, XsKey
except ImportError as e:
    print("The class XenStore won't be available due to missing dependency")
    print(str(e))

try:
    from ._libvirt_helper import LibvirtHelper
except ImportError as e:
    print("The class LibvirtHelper won't be available due to missing dependency")
    print(str(e))

from ._configuration_helper import Configuration, ConfigurationHelper
from ._system import System, topology

try:
    from ._keymap_fr import KeymapFR
except Exception as e:
    print("The class KeymapFR won't be available due to missing dependency")
    print(str(e))

from ._topics import Topics
from ._mqtt_helper import MqttHelper
from ._mqtt_client import MqttClient, ConnectionType, SerialMQTTClient
from ._request_factory import RequestFactory
from ._logger import Logger
from ._notification_factory import NotificationFactory
from ._file_helper import FileHelper
from ._response_factory import ResponseFactory

try:
    from ._disk_monitor import DiskMonitor
except ImportError as e:
    print("The class DiskMonitor won't be available due to missing dependency")
    print(str(e))

from ._mouse import Mouse, MouseButton, MouseWheel, MouseMove
from ._tasks_runner import TaskRunner
from ._inputs_daemon import InputsDaemon
from ._dom0_controller import Dom0Controller
from ._components_helper import ComponentsHelper
from ._mqtt_factory import MqttFactory
from ._api import Api
from ._debugging import Debugging
from ._api_helper import ApiHelper
from ._sys_usb_controller import SysUsbController
from ._mock_sys_usb_controller import MockSysUsbController

__all__ = [
    "__version__",
    "SingletonMeta",
    "Topology", "Domain", "DomainType", "DiskState",
    "XenStore", "XsDomain", "XsKey", 
    "Constants", "System", "topology", "Screen", "Constants", "ComponentState", "Topics", "Settings",
    "KeymapFR",
    "InputType", 
    "XcbController",
    "Configuration", "ConfigurationHelper",
    "RequestFactory",
    "LibvirtHelper",
    "Logger", "SysLogger",
    "NotificationFactory", 
    "ResponseFactory",    
    "FileHelper",    
    "InputsDaemon",
    "Mouse", "MouseButton", "MouseWheel", "MouseMove",
    "BenchmarkId",
    "TaskRunner",
    "MqttClient", "ConnectionType", "MqttFactory", "SerialMQTTClient", "MqttHelper",
    "Dom0Controller", "DiskMonitor", "Api",
    "ComponentsHelper",
    "Debugging", "ApiHelper",
    "SysUsbController", "MockSysUsbController",    
]

logging.getLogger(__name__).addHandler(NullHandler())