""" \author Tristan Israël """

import os
from . import Topology, SysLogger

class Configuration():
    """ This class encapsulates the data of a configuration 
    
    A configuration is made of:
    - a name (field `name`)
    - an identifier for the hardware (field `identifier`)
    - a set of parameters (field `settings`)
    """

    name = ""
    identifier = {}
    settings = {}

    def __init__(self, name:str, identifier:dict, settings:dict):
        self.name = name
        self.identifier = identifier
        self.settings = settings


class ConfigurationHelper():
    """ This class handles different sets of parameters defined for hardware configurations.
    """

    @staticmethod
    def apply_configuration(topology:Topology) -> Topology:
        """ Returns the configuration for the running system.

        The configuration returned will be composed of the keys from topology.json:
        - the global configuration (all keys except "configuration")
        - the specific configuration which matches the identifier defined in the configuration section

        The global settings are loaded and then overwritten by a specific configuration settings if any is applicable.

        Some settings cannot be overwritten:
        - product name
        - domains
        - configurations
        - vpcu
        """

        #configs = topology_struct.get("configurations", [])

        # Get the defaul topology
        #topology = ConfigurationHelper.__parse_topology(topology_struct)

        # Now we look at a configuration to apply and override some of
        # the settings
        #topo_confs = topology_struct.get("configurations", [])
        topo_confs = topology.configurations

        configurations = ConfigurationHelper.__read_configurations(topo_confs)

        if len(configurations) == 0:
            # If there is no configuration, we stop there
            return topology

        # Then we parse the configurations
        for conf in configurations:
            # We check all the settings
            # This dict will contain all keys searches and the result
            # By default all results are False
            settings = {k: False for k in conf.identifier}

            for key, value in conf.identifier.items():
                filename = f"/sys/class/dmi/id/{key}"

                if not os.path.exists(filename):
                    SysLogger("Configuration helper").warn(f"The sysfs file {filename} does not exist")
                    # So we ignore this key
                    continue

                system_value = ConfigurationHelper.__read_dmi_file(filename)

                # We compare the system value and the configuration's value
                if system_value == value:
                    settings[key] = True

            # If all settings are True it means that the current system
            # matches the configuration
            if all(settings.values()):
                ConfigurationHelper.__merge_configuration(topology, conf.settings)
                break
            
        # Finally we return the topology with the configuration applied
        return topology    

    @staticmethod
    def __read_configurations(topo:list[dict]) -> list[Configuration]:
        confs = []

        for conf_name in topo:
            topo_conf = topo[conf_name]
            conf = Configuration(
                conf_name,
                topo_conf.get("identifier", {}),
                topo_conf.get("settings", {})
            )

            confs.append(conf)

        return confs

    @staticmethod
    def __merge_configuration(topo:Topology, conf:dict):

        # USB section
        usb = conf.get("usb", None)
        if usb is not None:
            if usb.get("use", None) is not None:
                topo.use_usb = usb.get("use")

        # GUI section
        gui = conf.get("gui", None)
        if gui is not None:
            if gui.get("use", None) is not None:
                topo.use_gui = gui.get("use")
                topo.gui.use = topo.use_gui
            if gui.get("app-package", None) is not None:
                topo.gui.app_package = gui.get("app-package")
            if gui.get("memory", None) is not None:
                topo.gui.memory = gui.get("memory")
            if gui.get("screen", None) is not None:
                screen = gui.get("screen")
                if screen.get("rotation", None) is not None:
                    topo.screen.rotation = screen.get("rotation")
            
        # PCI section
        pci = conf.get("pci", None)
        if pci is not None:
            blacklist = pci.get("blacklist", None)
            if blacklist is not None:
                topo.pci.blacklist = blacklist

    @staticmethod
    def __read_dmi_file(filename:str) -> str:
        with open(file=filename, mode='r',encoding="utf-8") as data:
            return data.readline().strip()
        
        return None