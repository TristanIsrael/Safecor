""" \author Tristan Israël """
# ruff: noqa: I001
import base64
from datetime import datetime
import logging
import os
import zlib
import syslog
from . import (
    MqttClient,
    SingletonMeta,
    Topics,
    MqttHelper,
    RequestFactory,
    System,
    Constants
)

class FileHandler:
    """ The class FileHandler is an inner class for the class :class:`Logger`.
    """

    def __init__(self, file_path, mode='w'):
        self.file_path = file_path
        self.mode = mode
        self.file = open(self.file_path, self.mode)        

        print(f"File {self.file_path} opened in {self.mode} mode.")

    def __del__(self):
        if self.file and not self.file.closed:
            self.file.close()
            Logger().debug(f"File {self.file_path} closed.")

    def write(self, data):
        if 'w' in self.mode or 'a' in self.mode and self.file is not None:
            self.file.write(data)
        else:
            Logger().error("File not opened in write mode.")

    def flush(self):
        if self.file is not None:
            self.file.flush()

    def read(self):
        if 'r' in self.mode and self.file is not None:
            return self.file.read()
        else:
            Logger().error("File not opened in read mode.")

    def close(self):
        if self.file is not None:
            self.file.close()

class Logger(metaclass=SingletonMeta):
    """ This class provides mechanisms for logging and recording log files 
    
        The logging facility is intended to store messages and write them in a log file if asked. 
        
        For sending logging messages the best practice is to use the class :class:`Api` and the functions :func:`Api.info`, 
        :func:`Api.debug`, :func:`Api.warning`, etc. The embedded core logger will handle all messages for a system.

        This class can be used for an additionnal facility for a system based on Safecor.        
    """

    __is_setup = False
    __is_recording = False
    __log_level = logging.INFO
    __filename = "/var/log/safecor.log"

    def __init__(self):
        self.__domain_name = ""
        self.__module_name = ""
        self.__mqtt_client = None

    def setup(self, module_name:str, mqtt_client:MqttClient, log_level:int = logging.INFO, recording:bool=False, filename:str=Constants.LOCAL_LOG_FILEPATH):
        """ Sets up the logging facility. 
        
            Args:
                module_name (str): The module information is free. A module should be considered as a logical part of the product or of a component.
                mqtt_client (str): The MQTT client that handles the connection to the broker.
                log_level (int): The minimum logging level that this facility will take into account. When the log level of a message is lower that this, it is ignored.
                recording (bool): If True, the logging messages received will be recorded in a file.
                filename (str): The path of the file that will record all filtered messages.

            .. seealso::
                - :mod:`logging` - Standard Python logging facility
        """

        if self.__is_setup:
            return
        
        self.__domain_name = System.domain_name()
        self.__module_name = module_name
        self.__mqtt_client = mqtt_client

        #self.__mqtt_client.add_connected_callback(self.__on_connected)
        self.__mqtt_client.add_message_callback(self.__on_message)

        self.__is_recording = recording
        self.__filename = filename

        if recording and self.__filename != "":
            print(f"Recording logs into logfile: {self.__filename}")
            self.__mqtt_client.subscribe(f"{Topics.EVENTS}/#")

        self.__is_setup = True

    def reset(self):
        """ Resets the logging instance """

        if self.__is_setup and os.path.exists(self.__filename):
            os.truncate(self.__filename, 0)

        if self.__mqtt_client is not None:
            self.__mqtt_client.unsubscribe_all()
            self.__mqtt_client.del_message_callback(self.__on_message)

        self.__is_recording = False
        self.__log_level = logging.INFO
        self.__filename = "/var/log/safecor.log"
        self.__is_setup = False

    def clear_log(self):
        """ Clears the current log """

        if os.path.exists(self.__filename):
            os.truncate(self.__filename, 0)

    def critical(self, description:str, module:str = ""):
        """ Sends a critical message """

        if not self.__is_setup:
            return
        payload = self.__create_event(module, description)
        self.__mqtt_client.publish("system/events/critical", payload)

    def error(self, description:str, module:str = ""):
        """ Sends an error message """

        if not self.__is_setup:
            return
        payload = self.__create_event(module, description)
        self.__mqtt_client.publish("system/events/error", payload)

    def warning(self, description:str, module:str = ""):
        """ Sends a warning message """

        if not self.__is_setup:
            return
        payload = self.__create_event(module, description)
        self.__mqtt_client.publish("system/events/warning", payload)

    def warn(self, description:str, module:str = ""):
        """ Sends a warning message 

            Synonym of :func:`warning`.
        """

        if not self.__is_setup:
            return
        self.warning(description, module)

    def info(self, description:str, module:str = ""):
        """ Sends an information message """

        if not self.__is_setup:
            return
        payload = self.__create_event(module, description)
        self.__mqtt_client.publish("system/events/info", payload)

    def debug(self, description:str, module:str = ""):
        """ Sends a debugging message """

        if not self.__is_setup:
            return
        payload = self.__create_event(module, description)
        self.__mqtt_client.publish("system/events/debug", payload)    

    def __create_event(self, module:str, description:str) -> dict :
        if not self.__is_setup:
            return {}
        
        now = datetime.now()
        dt = now.strftime(f"%Y-%m-%d %H:%M:%S.{now.microsecond // 1000:03d}")

        payload = {
            "component": self.__domain_name,
            "module": module if module != "" else self.__module_name,
            "datetime": dt,
            "description": description
        }

        return payload

    def __on_message(self, topic:str, payload:dict):
        if topic == Topics.SET_LOG_LEVEL:
            self.__log_level = payload.get("level", "info")
        elif topic == Topics.SAVE_LOG and self.__is_recording:
            if not MqttHelper.check_payload(payload, ["disk", "filename"]):
                self.error("Missing required arguments: disk, filename")
                return
            
            disk = payload.get("disk", "")
            filename = payload.get("filename", "logfile.txt")
            # Prepend filename with a / if needed
            if not filename.startswith("/"):
                filename = "/"+filename
            
            self.info(f"Copying the log file to {disk}:{filename}")
            
            # Read all the data
            with open(self.__filename, "rb") as file:
                content = file.read()

            # Compress the data
            compressed_data = zlib.compress(content, level=1)  # 1-9

            # Create the file
            request = RequestFactory.create_request_create_file(filename, disk, base64.b64encode(compressed_data), True)
            self.__mqtt_client.publish(f"{Topics.CREATE_FILE}/request", request)
        elif self.__is_recording:
            # Log message
            self.__write_log(topic, payload)
 
    def __write_log(self, topic:str, payload:dict):
        if not self.__is_recording or self.__filename == "":
            return
        
        loglevel = "UNKNOWN"
        logtxt = ""

        # Extract the log level
        spl = topic.split("/")
        if len(spl) == 0:
            return
        spl.reverse()
        loglevel = spl[0]

        if self.__log_level > self.__loglevel_value(loglevel):
            return

        # Craft the log text
        # Fields are: module, datetime, level, description
        _datetime = payload.get("datetime")
        _module = payload.get("module")
        _description = payload.get("description")
        logtxt = f"[{_datetime}] [{loglevel}] {_module} - {_description}\n"
        #print(logtxt)
        logfile = FileHandler(self.__filename, 'a')
        logfile.write(logtxt)
        logfile.flush()
        logfile.close()

    def __loglevel_value(self, level:str) -> int:
        if level == "debug":
            return logging.DEBUG
        elif level == "info":
            return logging.INFO
        elif level == "warn" or level == "warning":
            return logging.WARN
        elif level == "error":
            return logging.WARN
        elif level == "critical":
            return logging.CRITICAL
        
        return logging.NOTSET
    
    @staticmethod
    def format_logline(message:str) -> str:
        """ Formats a message in the log file 
        
            The default format is ``%y-%m-%d %H:%M:%S.%f - Message text``

            Example:
            :: 
                2025-01-25 13:12:31.123 - The system has started
        """
        return f"{datetime.now():%Y-%m-%d %H:%M:%S.%f} - {message}"
    
    @staticmethod
    def print(message:str) -> None:
        """ Prints a formatted log in the standard output 
        
            .. seealso::
                - :func:`format_logline` - Log line format
        """
        print(Logger.format_logline(message))

    def is_setup(self) -> bool:
        return self.__is_setup
    
    def filename(self) -> str:
        return self.__filename
    
    def domain_name(self) -> str:
        return self.__domain_name
    
    def log_level(self):
        return self.__log_level
    
    def set_log_level(self, log_level):
        self.__log_level = log_level
    
    def is_recording(self):
        return self.__is_recording
    
    def module_name(self):
        return self.__module_name
    