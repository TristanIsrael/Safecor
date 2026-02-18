""" \author Tristan Israël """

import os
import libvirt
from . import Domain, DomainType

class LibvirtHelper():

    @staticmethod
    def get_domains() -> dict:
        """ @brief Returns the list of Domains declared on the system and their status """

        domains = {}

        conn = LibvirtHelper.__open_readonly()
        if conn is False:
            return domains

        for dom_id in conn.listDomainsID():
            dom_conf = conn.lookupByID(dom_id)
            dom = Domain(dom_conf.name(), DomainType.CORE if dom_conf.name().startswith("sys-") else DomainType.BUSINESS)
            
            dom.id = dom_id
            dom.memory = round(dom_conf.info()[2] / 1024)
            dom.vcpus = dom_conf.maxVcpus()

            # CPU affinity
            _, cpu_map = dom_conf.vcpus()
            for _, cpu_map in enumerate(cpu_map):
                allowed_pcpus = [i for i, allowed in enumerate(cpu_map) if allowed]
                dom.cpu_affinity = allowed_pcpus

            domains[dom.name] = dom

        conn.close()

        return domains

    @staticmethod
    def get_domains_count() -> int:
        """ @brief Returns the number of domains """

        conn = LibvirtHelper.__open_readonly()
        if conn is False:
            return 0

        cnt = conn.numOfDomains()
        conn.close()

        return cnt

    @staticmethod
    def get_cpu_count() -> int:
        """ @brief Returns the number of CPU in the system 
        
            In case of error the function returns 0.
        """
        
        conn = LibvirtHelper.__open_readonly()
        if conn is False:
            return 0
        
        info = conn.getInfo()
        if info is None:
            print("ERROR: Could not get information about the host")
            conn.close()
            return 0

        count = info[2]
        conn.close()

        return count
    
    @staticmethod
    def get_cpu_allocation_for_domain(domain_name:str) -> list:
        domains = LibvirtHelper.get_domains()

        dom = domains.get(domain_name, None)

        if dom is None:
            return []
        
        return dom.cpu_affinity

    @staticmethod
    def reboot_domain(domain_name:str) -> bool:
        """ @brief Reboots a domain.
         
            Returns True if the reboot has been acknowledged by the hypervisor 
        """

        result = False
        conn = LibvirtHelper.__open_readwrite()

        try:
            dom = conn.lookupByName(domain_name)
            dom.reboot()
            # TODO: Can we get more information?
        except libvirt.libvirtError:
            print(f"ERROR: Could not access domain {domain_name}")
            conn.close()
            return False

        conn.close()
        return result

    @staticmethod
    def __open_readonly() -> libvirt.virConnect|bool:
        mocked_libvirt = os.environ.get("MOCK_LIBVIRT")

        try:
            conn = libvirt.openReadOnly("test:///default" if mocked_libvirt else "xen:///")
            return conn
        except libvirt.libvirtError as e:
            print("ERROR: Could not open connection (RO) to libvirt")
            print(e)
            return False

    @staticmethod
    def __open_readwrite() -> libvirt.virConnect|bool:
        mocked_libvirt = os.environ.get("MOCK_LIBVIRT")

        if mocked_libvirt is True:
            print("Libvirt is mocked")

        try:
            conn = libvirt.open("test:///default" if mocked_libvirt else "xen:///")
            return conn
        except libvirt.libvirtError as e:
            print("ERROR: Could not open connection (RW) to libvirt")
            print(e)
            return False
