""" \author Tristan Israël """

import subprocess
import platform
import os
import json
import threading
try:
    import psutil
except ImportError:
    pass
import shutil
from . import SingletonMeta, __version__, Constants, Topology, DomainType, ConfigurationHelper, Domain
try:
    from . import LibvirtHelper
except ImportError:
    print("Not using Libvirt")
try:
    from inotify_simple import INotify, flags 
except Exception:
    print("The inotify library is not available on this system")

topology = Topology()

class System(metaclass=SingletonMeta):
    """ The System class provides functions for querying or modifying the system's state. 
    
        Some of the functions belong to the main system (Dom0) and some other belong to the virtual machines (DomU)
    """

    __DEFAULT_SCREEN_SIZE = "1100,750"
    __width = -1
    __height = -1
    __rotation = -1
    __system_uuid = ""
    __cpu_count = None
    __cpu_assignments = None

    def get_screen_width(self) -> int:
        """ Returns the system main screen's resolution width 

        This function must be ran in a DomU.
        """

        if self.__width > -1:
            return self.__width
        
        screen_size = self._get_screen_size()

        if "," in screen_size:
            rotation = self.get_screen_rotation()
            if rotation == 0 or rotation == 180:
                self.__width = int(screen_size.split(',')[0])
            else:
                self.__width = int(screen_size.split(',')[1])

            return self.__width
        
        return 1024
    
    def get_screen_height(self):
        """ Returns the system main screen's resolution height 
            
        This function must be ran in a DomU.
        """

        if self.__height > -1:
            return self.__height
        
        screen_size = self._get_screen_size()

        if "," in screen_size:            
            rotation = self.get_screen_rotation()
            if rotation == 0 or rotation == 180:
                self.__height = int(screen_size.split(',')[1])
            else: 
                self.__height = int(screen_size.split(',')[0])

            return self.__height
        
        return 768

    def get_screen_rotation(self) -> int:
        """ Returns the Domain's screen rotation angle 
        
            The rotation angle is defined in the topology file in the setting ``gui.screen.rotation``.

            This function must be ran in a DomU.

            Possible values are: 0, 90, 180, 270.
        """

        if self.__rotation > -1:
            return self.__rotation
        
        try:
            res = subprocess.run(["xenstore-read", "/local/domain/system/screen_rotation"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return int(res.stdout)
        except Exception:
            return 0
        
        return 0

    def _get_screen_size(self) -> str:
        """ Returns the Domain's screen size as a string.

            This function must be ran in a DomU.
         
            A typical value is: "1280x1024"
        """

        try:
            res = subprocess.run(["xenstore-read", "/local/domain/system/screen_size"], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            return self.__DEFAULT_SCREEN_SIZE    
        
        return self.__DEFAULT_SCREEN_SIZE
    
    def get_system_uuid(self):
        """ Returns the system's UUID 
        
            The UUID is queried from the Linux kernel's ``/sys/class/dmi/id/product_uuid``
        """

        system = platform.system().lower()

        # If we have it in cache...
        if self.__system_uuid != "":
            return self.__system_uuid
        
        if system == 'linux':
            try:
                with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                    self.__system_uuid = f.read().strip()
            except FileNotFoundError:
                return ""  # UUID is not available on this machine
            except PermissionError:
                return ""  # UUID reading is not autorized
        
        elif system == 'windows':
            try:
                output = subprocess.check_output('wmic csproduct get uuid', shell=True)
                lines = output.decode().split('\n')
                uuid = [line.strip() for line in lines if line.strip() and "UUID" not in line]
                self.__system_uuid = uuid[0] if uuid else ""
            except subprocess.CalledProcessError:
                return ""  # Erreur lors de l'exécution de wmic
        
        elif system == 'darwin':  # macOS
            try:
                output = subprocess.check_output('ioreg -rd1 -c IOPlatformExpertDevice', shell=True)
                for line in output.decode().split('\n'):
                    if 'IOPlatformUUID' in line:
                        self.__system_uuid = line.split('"')[-2]
                return ""
            except subprocess.CalledProcessError:
                return ""  # Erreur lors de l'exécution de ioreg
        
        return self.__system_uuid

    def get_platform_cpu_count(self) -> int:
        """ Returns the CPU count of the machine 
        
            The CPU count includes all cores.
        """

        if self.__cpu_count is not None:
            return self.__cpu_count
        
        self.__cpu_count = LibvirtHelper.get_cpu_count()

        return self.__cpu_count

    @staticmethod
    def debug_activated():
        """ Returns whether the debugging has been activated 
        
            This function must be ran in the Dom0.
        """

        try:
            fd = os.open("/proc/cmdline", os.O_RDONLY)
            data = os.read(fd, 4096)
            return b'debug=on' in data.lower()
        except Exception:
            return False
        
    @staticmethod
    def domain_name():
        """ Returns the Domain's name 
        
            This function must be ran in a DomU.
        """
        return platform.node()

    @staticmethod
    def reset_topology():
        """ Resets the current topology """

        global topology
        topology = Topology()

    @staticmethod
    def get_topology(override_topology_file:str = "") -> Topology:
        """ Returns a ``Topology`` object initialized with the contents of the topology file 
        
            This function must be ran in the Dom0.
        """

        global topology
        if not topology.initialized():
            # Initialize the topology object with the default configuration
            # We use the abstract struct returned by get_topology_struct()
            topo_struct = System.get_topology_struct(override_topology_file)
            topo = System.__parse_topology(topo_struct)
            topology = ConfigurationHelper.apply_configuration(topo)

            topology.set_initialized(True)

        return topology

    @staticmethod
    def __parse_topology(topo:dict) -> Topology:
        _topology = Topology()

        # Product information
        _topology.product_name = topo.get("product", {}).get("name", "Unknown")
        _topology.add_color("splash_bgcolor", topo.get("product", {}).get("splash_bgcolor", "#000000"))

        # System information
        _topology.use_usb = topo.get("system", {}).get("use_usb", False)
        _topology.use_gui = topo.get("system", {}).get("use_gui", False)
        _topology.screen.rotation = topo.get("system", {}).get("screen_rotation", 0)
        screen = System.get_framebuffer_dimension()
        _topology.screen.width = screen[0] if screen is not None else 0
        _topology.screen.height = screen[1] if screen is not None else 0
        _topology.uuid = System().get_system_uuid()
        _topology.gui.app_package = topo.get("system", {}).get("gui_app_package", "error")
        _topology.gui.memory = topo.get("system", {}).get("gui_memory", 2000)
        _topology.gui.use = _topology.use_gui
        _topology.pci.blacklist = topo.get("system", {}).get("pci", {}).get("blacklist", [])

        # Domains information
        domains = topo.get("domains", {})
        for domain_name, domain_desc in domains.items():
            domain = Domain(domain_name, domain_desc.get("type", DomainType.UNKNOWN))
            domain.vcpu_group = domain_desc.get("vcpu_group", "")
            domain.memory = domain_desc.get("memory", 0)
            domain.vcpus = domain_desc.get("vcpus", "")
            domain.cpu_affinity = domain_desc.get("cpus", []) #System.parse_range(domain.vcpus)
            domain.package = domain_desc.get("package", "")

            _topology.add_domain(domain)

        # Configurations
        _topology.configurations = topo.get("configurations", [])

        return _topology

    @staticmethod
    def parse_range(value: str) -> tuple[int, ...]:
        """ Converts an int range represented as a string into a tuple of all values between min and max
        
            Examples:
                >>> parse_range("1-2") 
                    (1,2)
                >>> parse_range("3-8") 
                    (3,4,5,6,7,8)

            The left value must be lower that the right value.
        """

        if value == "":
            return ()

        if "-" in value:
            start, end = map(int, value.split("-", 1))
            if start > end:
                raise ValueError("Invalid range")
            return tuple(range(start, end + 1))
        return (int(value),)

    @staticmethod
    def get_topology_struct(override_topology_file:str = "") -> dict:
        """ Returns the topology of the current system

        The topology structure is different from the configuration file topology.json because the file will
        evolve from its original format and it must be dissociated from the internal structure to avoid
        future compatibility problems.

        The topology is defined in the file `topology.json`. This function returns a data structure
        representing the topology as a dict. Instead of returning the JSON data as the function 
        :func:`read_topology_file` does, it returns a structure representing the objects: 
        
        ::

            {
                "domains": [
                    "my-domain": {
                        "vcpu_group": "group1",
                        "memory": 4000,
                        "vcpus": 2,
                        "cpus": "3-4",
                        "package": ""
                    }
                ],
                "system": {
                    "use_usb": 1,
                    "use_gui": 1,
                    "screen_rotation": 0,
                    "gui_app_package": "",
                    "gui_memory": 1000,
                },
                "product": {
                    "name": "Safecor"
                },
                "configurations": [
                    {
                        "name": "",
                        ...
                    }
                ]
            }

        All the keys are guaranteed to exist with a default value if necessary.
        """
        
        topo_data = System.get_topology_data(override_topology_file)
        if topo_data is None:
            print("No topology data available. Aborting.")
            return {}
        
        topo_struct = System.__analyse_topology_struct(topo_data)
        return topo_struct
        
    @staticmethod
    def __analyse_topology_struct(topo_data:dict) -> dict:
        topo_struct = {}

        usb = topo_data.get("usb", {})
        gui = topo_data.get("gui", {})
        screen = gui.get("screen", {})
        vcpu = topo_data.get("vcpu", {})
        business = topo_data.get("business", {})
        business_domains = business.get("domains", [])

        topo_data_pci = topo_data.get("pci", {})
        pci_blacklist = topo_data_pci.get("blacklist", [])

        use_usb = usb.get("use", False)
        use_gui = gui.get("use", False)
        gui_app_package = gui.get("app-package", "")
        screen_rotation = screen.get("rotation", 0)
        gui_memory = gui.get("memory", 128)
                
        topo_struct["system"] = {
            "use_usb": use_usb,
            "use_gui": use_gui,
            "screen_rotation": screen_rotation,
            "gui_app_package": gui_app_package,
            "memory": gui_memory,
            "pci": {
                "blacklist": pci_blacklist
            }
        }

        vcpu_groups = vcpu.get("groups", {})

        topo_domains = {}

        # sys-usb domain
        topo_domains["sys-usb"] = {
            "name": "sys-usb",
            "type": DomainType.CORE,
            "memory": 350,
            "vcpus": System.compute_vcpus_for_group("sys-usb", vcpu_groups),
            "cpus": System().compute_cpus_for_group("sys-usb", vcpu_groups),
            "vcpu_groups": vcpu_groups
        }

        # sys-gui domain
        topo_domains["sys-gui"] = {
            "name": "sys-gui",
            "type": DomainType.CORE,
            "memory": gui.get("memory"),
            "vcpus": System.compute_vcpus_for_group("sys-gui", vcpu_groups),
            "cpus": System().compute_cpus_for_group("sys-gui", vcpu_groups),  
            "vcpu_groups": vcpu_groups          
        }
        
        for domain in business_domains:
            # Business domains
            domain_name = domain.get("name", "unknown")
            group_name = domain.get("vcpu_group", domain_name) # If there is no group we will create a default configuration
            topo_domains[domain_name] = {
                "name": domain.get("name", "unknown"),
                "type": DomainType.BUSINESS,
                "memory": domain.get("memory", 0),
                "package": domain.get("app-package", ""),
                "vcpus": System.compute_vcpus_for_group(group_name, vcpu_groups),
                "cpus": System().compute_cpus_for_group(group_name, vcpu_groups),
                "vcpu_groups": vcpu_groups
            }

        topo_struct["domains"] = topo_domains

        # Get product information (copy)
        json_product = topo_data.get("product", {})
        topo_product = {}
        topo_product["name"] = json_product.get("name", "No Name")
        topo_product["splash_bgcolor"] = json_product.get("splash_bgcolor", "#1ca9f7")
        topo_struct["product"] = topo_product

        # Get the configurations settings
        data_configurations = topo_data.get("configurations", [])
        topo_configurations = {}
        for data_conf in data_configurations:
            conf_name = data_conf.get("name", "noname")
            conf_identifier = data_conf.get("identifier", {})
            conf_settings = data_conf.get("settings", {})

            topo_configurations[conf_name] = {
                "identifier": conf_identifier,
                "settings": conf_settings
            }
        
        topo_struct["configurations"] = topo_configurations

        return topo_struct


    @staticmethod
    def read_topology_file(override_topology_file:str = "") -> str:
        """ Reads the topology file describing the product 
        
            This function must be ran in the Dom0.
        """

        filepath = '/etc/safecor/topology.json' if override_topology_file == "" else override_topology_file
        try:
            with open(filepath, 'r') as f:
                topo = f.read()
                f.close()
                return topo
        except Exception as e:
            print(f"An error occured while reading the topology file at {filepath})")
            print(e)
            return ""

    @staticmethod
    def get_topology_data(override_topology_file:str = "") -> dict:
        """ Interprets the topology file data as a JSON object 
        
            This function must be ran in the Dom0.
        """

        try:
            topo_data = System.read_topology_file(override_topology_file)
            data = json.loads(topo_data)
            return data
        except Exception as e:
            print("An error occured while decoding JSON file")
            print(e)
            return {}
        

    @staticmethod
    def compute_vcpus_for_group(group_name:str, groups:dict) -> int:
        """ Computes the number of vCPUs which will be pinned to each Domain of a group.

        The number of vCPUs depends on the value of the parameter ``vcpu.groups`` defined in the file ``topology.json``.

        This function must be ran in the Dom0.
        """
        vcpus = 1
        platform_cpus = System().get_platform_cpu_count()
        dom0_vcpus = 2 if platform_cpus > 4 else 1
        sys_usb_vcpus = 0 #Dom0 and sys-usb share the same vcpus

        if group_name == "sys-usb":
            return dom0_vcpus

        reserved_vcpus = dom0_vcpus + sys_usb_vcpus

        # If there is no group defined we force the cpu count
        if len(groups) == 0:
            #print(f"There is no group for {group_name}")
            #print(platform_cpus, reserved_vcpus)
            return platform_cpus - reserved_vcpus

        if group_name in groups:
            vcpu_rate = groups.get(group_name, None)

            # Override cpu rate for sys-gui if not provided
            vcpu_rate = 0.2 if vcpu_rate is None and group_name == "sys-gui" else vcpu_rate

            if vcpu_rate is not None:
                vcpus = int(round(vcpu_rate*(platform_cpus-reserved_vcpus), 0))
                return max(vcpus, 1)
        else:
            # If there is no group defined we consider using 100% of the remaining cores
            #print(f"default case for {group_name}:{platform_cpus - reserved_vcpus}")
            return platform_cpus - reserved_vcpus

        return vcpus

    def compute_cpus_for_group(self, group_name:str, groups:dict) -> list[int]:
        """ Computes the CPUs (or cores) which will be pinned to the Domains of the group.

        The first CPU is assigned to Dom0 and sys-usb Domain. 
        
        If there are at least 4 CPUs the second CPU is also assigned to Dom0 and sys-usb.
        
        The other CPUs are assigned to sys-gui and the other groups by trying to avoid overlapping.

        This function must be ran in the Dom0.
        """        
        cpu_count = System().get_platform_cpu_count()

        if group_name not in groups and group_name not in [ "sys-usb", "Dom0" ]:
            # If the group does not exist we return the default configuration
            return list(range(1 if cpu_count <= 4 else 2, cpu_count))

        if self.__cpu_assignments is not None:
            # If the groups are in cache we take them
            cpu_assignments = self.__cpu_assignments
        else:
            # Otherwise we calculate them before
            cpu_assignments = {
                "Dom0": [ 0 ],
                "sys-usb": [ 0 ],
                "sys-gui": [ 1 ]
            }

            next_pin = 1
            if cpu_count > 4:
                # If there are more than 4 CPUs/cores we add one to Dom0 and sys-usb
                cpu_assignments["Dom0"].append(next_pin)
                cpu_assignments["sys-usb"].append(next_pin)
                next_pin += 1

            # Then we assign sys-gui
            if cpu_count > 4:
                vcpus = System.compute_vcpus_for_group("sys-gui", groups)
                cpu_assignments["sys-gui"] = list(range(2, next_pin + vcpus))
                next_pin += 2

            # Then the other groups
            for gname in groups.keys():
                if gname in [ "sys-gui" ]:
                    continue # We ignore sys-gui because we already worked on it
                
                vcpus = System.compute_vcpus_for_group(gname, groups)
                cpu_assignments[gname] = list(range(next_pin, next_pin + vcpus))

            self.__cpu_assignments = cpu_assignments

        # Finally we return the value
        return cpu_assignments.get(group_name, [ 0 ])

    @staticmethod
    def get_system_information() -> dict:
        """ Returns a JSON struct containing the information on the system. 

            This function must be ran in the Dom0.
        
            A typical struct is:

            ::

                {
                "core": {
                    "version": "1.1", 
                    "debug_on": false
                }, 
                "system": {
                    "os": {
                        "name": "Linux", 
                        "release": "6.12.20-0-lts", 
                        "version": "#1-Alpine SMP PREEMPT_DYNAMIC 2025-03-24 08:09:11"
                    }, 
                    "machine": {
                        "arch": "x86_64", 
                        "processor": "", 
                        "platform": "Linux-6.12.20-0-lts-x86_64-with", 
                        "cpu": {
                            "count": 12, 
                            "freq_current": 1689.5960000000002, 
                            "freq_min": 0.0, 
                            "freq_max": 0.0, 
                            "percent": 0.0
                        }, 
                        "memory": {
                            "total": 405987328, 
                            "available": 96657408, 
                            "percent": 76.2, 
                            "used": 256733184, 
                            "free": 12472320
                        }, 
                        "load": {
                            "1": 0.5244140625, 
                            "5": 0.21875, 
                            "15": 0.08154296875
                        }
                    }, 
                    "boot_time": 1748036696.0, 
                    "uuid": "11ec0800-4fb9-11ef-bd38-ad993f2e7700"
                    "storage": {
                        "total": 12345678,
                        "used": 0,
                        "free": 12345678,
                        "files_count": 0
                    }
                }
            }
        """

        sysinfo = {
            "core": {
                "version": __version__,
                "debug_on": System.debug_activated()
            },
            "system": {
                "os" : {
                    "name": platform.system(),
                    "release": platform.release(),
                    "version": platform.version()
                },
                "machine": {
                    "arch": platform.machine(),
                    "processor": platform.processor(),
                    "platform": platform.platform(),
                    "cpu": {
                        "count": System().get_platform_cpu_count(),
                        "freq_current": psutil.cpu_freq().current,
                        "freq_min": psutil.cpu_freq().min,
                        "freq_max": psutil.cpu_freq().max,
                        "percent": psutil.cpu_percent()
                    },
                    "memory": {
                        "total": psutil.virtual_memory().total,
                        "available": psutil.virtual_memory().available,
                        "percent": psutil.virtual_memory().percent,
                        "used": psutil.virtual_memory().used,
                        "free": psutil.virtual_memory().free
                    }
                },
                "storage": System.__get_storage_info(),
                "boot_time": psutil.boot_time(),
                "uuid": System().get_system_uuid(),
                "cpu_allocation": System().get_cpu_allocation()
            }
        }
 
        # Special case for Windows
        if hasattr(os, "getloadavg"):
            sysinfo["system"]["machine"]["load"] = {
                "1": os.getloadavg()[0],
                "5": os.getloadavg()[1],
                "15": os.getloadavg()[2]
            }

        return sysinfo
    
    @staticmethod
    def __get_storage_info() -> dict:
        """ Returns information about the storage 

        This function must be ran in the Dom0.
        
        The fields are:
        - total - The total size of the storage in bytes
        - used - The used space of the storage in bytes
        - free - The free space of the storage in bytes
        - files - The number of files in the storage
        """

        info = {
            "total": 0,
            "used": 0,
            "free": 0,
            "files": 0
        }

        storage_path = Constants.DOM0_REPOSITORY_PATH
        print(f"Looking for storage information into {storage_path}")

        # Get information about the disk
        try:
            if storage_path is not None:
                usage = shutil.disk_usage(storage_path)
                info["total"] = usage.total
                info["used"] = usage.used
                info["free"] = usage.free
        except Exception as e:
            print(f"Could not get storage information : {e}")

        # Get information about the files
        if storage_path is not None:
            for _, _, files in os.walk(storage_path):
                info["files"] += len(files)

        return info

    def get_cpu_allocation(self) -> dict:
        """ Provides information about CPU allocation for all the Domains 
        
            This function must be ran in the Dom0.
        """

        cpu_alloc = {}

        # First get the list of domains
        domains = LibvirtHelper.get_domains()

        for domain in domains.values():
            cpu_alloc[domain.name] = domain.cpu_affinity

        return cpu_alloc

    @staticmethod
    def cpu_affinity_to_string(cpu_affinity:list) -> str:
        """ Converts the cpu affinity of the Domain definition to a string 
        
            Example:
            >>>
                cpu_affinity_to_string([1,2,3,4])
                '1-4'
        """

        if len(cpu_affinity) == 0:
            return ""
        elif len(cpu_affinity) == 1:
            return str(cpu_affinity[0])
        return f"{cpu_affinity[0]}-{cpu_affinity[-1]}"
    
    @staticmethod
    def get_framebuffer_dimension(fbdev:int = 0) -> tuple[int, int]:
        """ Returns the framebuffer dimensions as a tuple (width, height) 
        
        By default, the framebuffer fb0 is queried. This can be overriden by setting the
        parameter fbdev
        """
        
        try:
            with open(f"/sys/class/graphics/fb{fbdev}/virtual_size") as f:
                data = f.read().strip()
            width, height = map(int, data.split(","))
            return width, height
        except FileNotFoundError:
            return (1100, 750)

    @staticmethod
    def get_screen_rotation_from_topology(override_topology_file:str = "") -> int:
        """ Returns the screen rotation defined in the topology file
        
        This function is necessary for treatments that occur before libvirt and xenstore
        are loaded. The function :func:`get_topology_struct` is one of those.
        """

        topo_data = System.get_topology_data(override_topology_file)
        gui = topo_data.get("gui", {})
        screen = gui.get("screen", {})
        rotation = screen.get("rotation", 0)

        return rotation

    @staticmethod
    def get_splash_bgcolor_from_topology(override_topology_file:str = "") -> int:
        """ Returns the background color for the plash defined in the topology file
        
        This function is necessary for treatments that occur before libvirt and xenstore
        are loaded. The function :func:`get_topology_struct` is one of those.
        """

        topo_data = System.get_topology_data(override_topology_file)
        product = topo_data.get("product", {})
        color = product.get("splash_bgcolor", "#000000")

        return color

    def monitor_file(self, path:str, filename:str, fn_callback):
        """
        Starts the monitoring of a single file or a whole directory.
         
        When a file is created or removed, the callback function is called with the following parameters:
        - path:str - The directory path
        - filename:str - The file name 
        - exists:bool - True if the file has been created, else False

        This function is uninterruptible.
        
        :param path: The directory to monitor
        :type path: str
        :param filename: A file name to monitor, set to None if the whole directory should be monitored
        :type filename: str
        :param fn_callback: The callback function
        """
        
        if fn_callback is None:
            print("Monitoring of file called without callback. Aborted.")
            return

        thread = threading.Thread(target=self.__monitor_file_worker, daemon=True, args=(path, filename, fn_callback,))
        thread.start()

    def __monitor_file_worker(self, path:str, filename:str, fn_callback):
        i = INotify()
        i.add_watch(path, flags.CREATE | flags.DELETE)

        while True:
            for event in i.read():
                (_, mask, _path, _filename) = event
                if filename is not None and filename != _filename:
                    continue
                
                present = flags.CREATE in flags.from_mask(mask)
                threading.Thread(target=fn_callback, args=(path, _filename, present,)).start()
            