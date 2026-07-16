""" \author Tristan Israël """

from typing import List
from enum import Enum
import copy

class DomainType(Enum):
    """ This enumeration defines a Domain"s type """
    UNKNOWN = 0
    CORE = 1
    BUSINESS = 2

class Domain:
    """ This class encapsulates information about a Domain """

    id = 0
    name = "NoName"
    vcpu_group = "group1"
    memory = 1000
    vcpus = 1
    cpu_affinity = [] # List of CPU pins
    package = ""
    domain_type = DomainType.BUSINESS
    temp_disk_size = 0
    swap_size = 0
    has_gui = False
    
    def __init__(self, domain_name:str, domain_type:DomainType):
        self.name = domain_name
        self.domain_type = domain_type

class Screen:
    """ This class encapsulates information about a screen """

    width = 0
    height = 0
    rotation = 0
    enabled = False
    default_focus = ""

class Pci:
    """ This class encapsulates information about the PCI buses of a system """

    blacklist = []

class Storage:
    """ This class encapsulates information about the local storage of a system """

    on_disk = False
    index = 1
    size = -1

class Topology:
    """ This class encapsulates and handles information about the topology of a product 
    
    The topology is usually defined in the file /etc/safecor/topology.json

    The topology object corresponds to the configuration that should be applied
    to the device. 
    """

    domains = List[Domain]
    product_name = "No Name"
    use_usb = False
    uuid = ""
    screen: Screen
    configurations = []
    pci: Pci
    languages = []
    default_language = "en"
    storage:Storage

    def __init__(self, other=None):
        """ Create a new Topology from scratch or as a deep copy if other is not None """

        if other is None:
            self.domains = []
            self.screen = Screen()
            self.pci = Pci()
            self.storage = Storage()
            self.__colors = {}
            self.__initialized = False
        else:
            self.domains = copy.deepcopy(other.domains)
            self.product_name = copy.deepcopy(other.product_name)
            self.use_usb = copy.deepcopy(other.use_usb)
            self.uuid = copy.deepcopy(other.uuid)
            self.screen = copy.deepcopy(other.screen)            
            self.configurations = copy.deepcopy(other.configurations)
            self.pci = copy.deepcopy(other.pci)
            self.languages = copy.deepcopy(other.languages)
            self.default_language = copy.deepcopy(other.default_language)
            self.storage = copy.deepcopy(other.storage)

    def initialized(self) -> bool:
        """ Returns whether the object is initialized """
        
        return self.__initialized
    
    def set_initialized(self, initialized:bool):
        """ Sets the objet initialized """
        
        self.__initialized = initialized
    
    def colors(self) -> dict:
        """ Returns the RGBA colors list as a list of 8 bit tuples (r, g, b, a)
        
        .. seealso::
            :func:`colors_as_hex`
        """

        vals = {}
        for name, color in self.__colors.items():
            vals[name] = self.color_as_rgba(color)

        return vals

    def colors_as_hex(self) -> dict:
        """ Returns the colors list as hexadecimal values (#rrggbbaa)
        
        .. seealso::
            :func:`colors`
        """
        
        colors = []

        for color in self.__colors:
            colors.append(self.color_as_hex(color))

        return colors
    
    def color_as_hex(self, color_name:str) -> str:
        """ Returns a named color as an hex value """
        
        color = self.__colors.get(color_name, (0,0,0,0))
        return self.__rgba_to_hex(color)
    
    def color_as_rgba(self, color_name:str) -> tuple[int, int, int, int]:
        """ Returns an RGBA named color as a tuple value """
        
        return self.__colors.get(color_name, (0,0,0,0))
    
    def add_color(self, color_name:str, color_value_as_hex:str):
        """ Adds a named color to the list """
        
        self.__colors[color_name] = self.__hex_to_rgba(color_value_as_hex)
    
    def __hex_to_rgba(self, hex_color: str) -> tuple[int, int, int, int]:
        """ Converts a color from hex to rgba tuple """
        
        hex_color = hex_color.lstrip("#")
        r = 0
        g = 0
        b = 0
        a = 0

        if len(hex_color) == 3:
            r = int(hex_color[0], 16) << 4 | int(hex_color[0], 16)
            g = int(hex_color[1], 16) << 4 | int(hex_color[1], 16)
            b = int(hex_color[2], 16) << 4 | int(hex_color[2], 16)
            a = 255
        elif len(hex_color) == 4:
            r = int(hex_color[0], 16) << 4 | int(hex_color[0], 16)
            g = int(hex_color[1], 16) << 4 | int(hex_color[1], 16)
            b = int(hex_color[2], 16) << 4 | int(hex_color[2], 16)
            a = int(hex_color[3], 16) << 4 | int(hex_color[3], 16)
        elif len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = 255
        elif len(hex_color) == 8:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)

        return (r,g,b,a)
    
    def __rgba_to_hex(self, color_as_rgba:tuple[int, int, int, int]) -> str:
        r = color_as_rgba[0]
        g = color_as_rgba[1]
        b = color_as_rgba[2]
        a = color_as_rgba[3]

        return f"#{r:0{2}x}{g:0{2}x}{b:0{2}x}{a:0{2}x}"

    def add_domain(self, domain:Domain):
        """ Adds a Domain's definition to the list """
        
        self.domains.append(domain)

    def domain_names(self) -> list:
        """ Returns the list of Domain names """
        
        return [d.name for d in self.domains]

    def domain(self, domain_name:str) -> Domain|None:
        """ Returns the Domain object with the specified name """

        if domain_name in self.domain_names():
            result = [d for d in self.domains if d.name == domain_name]
            if len(result) > 0:
                return result[0]
        
        return None
    
    def business_domains(self) -> list[Domain]:
        """ Returns only the business domains """

        doms = []

        for dom in self.domains:
            if dom.domain_type == DomainType.BUSINESS:
                doms.append(dom)

        return doms
    
    def is_pci_bus_blacklisted(self, bus_bdf:str) -> False:
        """ Returns true if the bus is in the blacklist """

        for d in self.pci.blacklist:
            if bus_bdf.endswith(d):
                return True
            
        return False

    def graphical_domains(self) -> list[Domain]:
        """ Returns all the domains that have graphical content """

        doms = []

        for dom in self.domains:
            if dom.has_gui:
                doms.append(dom)

        return doms
    
    def default_focus(self) -> str:
        """ Returns the name of the Domain that has the default focus """

        default_focus = self.screen.default_focus
        gui_domains = self.graphical_domains()
        if default_focus == "" and len(gui_domains) > 0:
            return gui_domains[0].name
        else:
            return default_focus
            
