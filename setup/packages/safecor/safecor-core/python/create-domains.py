''' @brief This file contains mechanims for creating new DomUs on a Safecor system
'''
import subprocess
import tempfile
import os
from safecor import (
    System, Domain, DomainType, SysLogger    
)

DEFAULT_SAFECOR_VIRT_ISO_FILEPATH = "/var/lib/xen/images/alpine-virt.iso"

class DomainsFactory:
    """ This class is designed to orchestrate the Domains creation during the
    setup process of a system based on Safecor.
    
    The Domains are defined in the file /etc/safecor/topology.json.
    """

    @staticmethod
    def create_domains():
        """ Creates all the Domains of a Safecor system """

        SysLogger("create-domains").info("Start creating domains from topology")

        topology = System.get_topology()

        if topology.use_usb:
            blacklist_conf = DomainsFactory.__create_blacklist_conf("sys-usb")
            DomainsFactory.__provision_domain("sys-usb", "safecor-sys-usb", "virt", blacklist_conf)
            DomainsFactory.__create_domd_usb()

        DomainsFactory.__create_business_domains()
        
        SysLogger("create-domains").info("Finished creating domains")


    ###
    # Private functions
    #
    @staticmethod
    def __create_domd_usb():
        SysLogger("create-domains").info("Create configuration for Driver Domain sys-usb")

        conf = DomainsFactory.__create_xl_conf_sys_usb()

        if conf is not None:
            filename = '/etc/safecor/xen/sys-usb.conf'
            with open(filename, 'w') as f:
                f.write(conf)

            try:
                os.chmod(filename, 0o770)
            except Exception as e:
                SysLogger("create-domains").info(f"Could not set permission on file {filename} : {e}")

        SysLogger("create-domains").info("Configuration for Domain sys-usb created successfully")

    
    @staticmethod
    def __create_business_domains():
        SysLogger("create-domains").info("Create all the business Domains")

        topology = System.get_topology()

        if len(topology.domains) > 0:
            for domain in topology.domains:
                domain: Domain
                SysLogger("create-domains").info(f"Creating domain {domain.name}")

                if domain.domain_type is not DomainType.BUSINESS:
                    continue

                package = domain.package

                blacklist_conf = DomainsFactory.__create_blacklist_conf()
                DomainsFactory.__provision_domain(domain.name, package, "virt", blacklist_conf)
                conf = DomainsFactory.__create_xl_conf_domain(
                    domain,
                    boot_iso_location= f"bootiso-{domain.name}.iso",
                    share_packages= True,
                    share_storage= True,
                    share_system= False,
                )

                filename = f"/etc/safecor/xen/{domain.name}.conf"
                with open(filename, 'w') as f:
                    f.write(conf)

                try:
                    os.chmod(filename, 0o770)
                except Exception as e:
                    SysLogger("create-domains").info(f"Could not set permission on file {filename} : {e}")

                DomainsFactory.__fetch_alpine_packages(package)

                SysLogger("create-domains").info(f"Domain {domain.name} created successfully")                
        else:
            SysLogger("create-domains").info("There are not business domains to create")

    @staticmethod
    def __create_xl_conf_sys_usb() -> None:
        topology = System.get_topology()

        sys_usb = topology.domain("sys-usb")

        txt = f'''
type = "hvm"
name = "sys-usb"
serial = "pty" 
memory= { sys_usb.memory }
vcpus = { sys_usb.vcpus }
cpus = "{ System.cpu_affinity_to_string(sys_usb.cpu_affinity) }"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=sdd, access=r, target=/usr/lib/safecor/system/sys-usb-config.img'
]
p9 = [
'tag=packages, path=/usr/lib/safecor/packages, backend=0, security_model=none',
'tag=storage, path=/usr/lib/safecor/storage, backend=0, security_model=none'
]
channel = [
#'name=console, connection=pty',
'name=sys-usb-msg, connection=socket, path=/var/run/safecor/sys-usb-msg.sock',
'name=sys-usb-input, connection=socket, path=/var/run/safecor/sys-usb-input.sock',
'name=sys-usb-tty, connection=socket, path=/var/run/safecor/sys-usb-tty.sock'
]
vga = "none"
device_model_override = "/usr/bin/qemu-system-x86_64"
device_model_version = "qemu-xen"
usb=0
vnc=0
vif=[]
'''

        return txt

    @staticmethod
    def __create_xl_conf_sys_gui() -> None:
        topology = System.get_topology()

        sys_gui = topology.domain("sys-gui")

        txt = f'''
type = "hvm"
name = "sys-gui"
serial = "pty" 
memory={ sys_gui.memory }
vcpus = { sys_gui.vcpus }
cpus = "{ System.cpu_affinity_to_string(sys_gui.cpu_affinity) }"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=sdd, access=r, target=/usr/lib/safecor/system/sys-gui-config.img'
]
p9 = [
    'tag=packages, path=/usr/lib/safecor/packages, backend=0, security_model=none',
    'tag=storage, path=/usr/lib/safecor/storage, backend=0, security_model=none'
]
channel = [
#'name=console, connection=pty',
'name=sys-gui-msg, connection=socket, path=/var/run/safecor/sys-gui-msg.sock',
'name=sys-gui-input, connection=socket, path=/var/run/safecor/sys-gui-input.sock'
]
vga = "none"
device_model_override = "/usr/bin/qemu-system-x86_64"
device_model_version = "qemu-xen"
device_model_args = [
     '-device', 'virtio-gpu-pci',
     '-display', 'gtk,full-screen=on,zoom-to-fit=on,gl=on',
     '-device', 'virtio-input-host,id=virtio-mouse,evdev=/var/run/safecor/virtual_mouse',
     '-device', 'virtio-input-host,id=virtio-keyboard,evdev=/var/run/safecor/virtual_keyboard',
     '-device', 'virtio-input-host,id=virtio-touch,evdev=/var/run/safecor/virtual_touch'
]
usb=0
vnc=0
vif=[]
'''

        return txt

    @staticmethod
    def __create_xl_conf_domain(domain:Domain, boot_iso_location:str, share_packages:bool=True, share_storage:bool=True, share_system:bool=False):
        topology = System.get_topology()
        
        dom = topology.domain(domain.name)

        txt = f'''
type = "hvm"
serial = "pty" 
boot = "d"
name = "{ domain.name }"
memory = { domain.memory }
vcpus = { domain.vcpus }
cpus = "{ System.cpu_affinity_to_string(dom.cpu_affinity) }"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=sdd, access=r, target=/usr/lib/safecor/system/{domain.name}-config.img'
'''
        # Add a temp diskfile if required
        # The diskfile is prepared by the orchestrator
        if domain.temp_disk_size > 0:
            txt += f", 'format=raw, vdev=sde, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-tmp.img'"

        # Add a swap diskfile if required
        # The diskfile is prepared by the orchestrator
        if domain.swap_size > 0:
            txt += f", 'format=raw, vdev=sde, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-swap.img'"

        txt += '''
]
device_model_override = "/usr/bin/qemu-system-x86_64"
device_model_version = "qemu-xen"
vnc=0
usb=0
vif=[]
'''

        # Add vGPU if needed
        if domain.has_gui:
            txt += f'''
vga = "none"
device_model_override = "/usr/bin/qemu-system-x86_64"
device_model_version = "qemu-xen"
device_model_args = [
     '-device', 'virtio-gpu-pci',
     '-display', 'gtk,full-screen=on,zoom-to-fit=on,gl=on',
     '-device', 'virtio-input-host,id=virtio-mouse,evdev=/var/run/safecor/virtual_mouse_{domain.name}',
     '-device', 'virtio-input-host,id=virtio-keyboard,evdev=/var/run/safecor/virtual_keyboard_{domain.name}',
     '-device', 'virtio-input-host,id=virtio-touch,evdev=/var/run/safecor/virtual_touch_{domain.name}'
]
'''
        
        # Add P9 shares
        shares = []
        #shares.append("'name=console, connection=pty'")
        if share_packages:
            shares.append("'tag=packages, path=/usr/lib/safecor/packages, backend=0, security_model=none'")
        if share_storage:
            shares.append("'tag=storage, path=/usr/lib/safecor/storage, backend=0, security_model=none'")
        if share_system:
            shares.append("'tag=system, path=/usr/lib/safecor/system, backend=0, security_model=none'")

        if len(shares) > 0:
            txt += "p9 = [\n{}\n]\n".format(",\n".join(shares))

        # Add serial channels
        channels = []
        channels.append(f"'name={domain.name}-msg, connection=socket, path=/var/run/safecor/{domain.name}-msg.sock'") # /dev/hvc1
        
        if len(channels) > 0:
            txt += "channel = [\n{}\n]\n".format(",\n".join(channels))

        return txt

    @staticmethod
    def __provision_domain(domain_name:str, main_package:str, alpine_branch:str = "virt", blacklist_conf:str = None):
        cmd = "/usr/lib/safecor/bin/provision-domain.sh"

        try:
            subprocess.run([cmd, domain_name, main_package, alpine_branch, blacklist_conf], check=True)

            # When finished we remove the blacklist.conf file
            os.unlink(blacklist_conf)
        except Exception as e:
            SysLogger("create-domains").error(f"An error occured during the provisioning of the domain {domain_name}")
            SysLogger("create-domains").error(e)

    @staticmethod
    def __fetch_alpine_packages(package):
        # Fetch Alpine packages
        if package is None:
            SysLogger("create-domains").error("No package name provided")
            return

        subprocess.run(
            args= ["apk", "fetch", "-R", package],
            cwd= "/usr/lib/safecor/packages/alpine/x86_64",
            check= True
        )

        subprocess.run(
            args= ["/usr/lib/safecor/bin/reindex-and-sign-repository.sh"],
            check= True
        )

###
### Private functions
    @staticmethod
    def __create_blacklist_conf(domain_name:str = "") -> str:
        SysLogger("DomainsFactory").info(f"Create blacklist.conf file for { domain_name if domain_name != "" else "standard Domain" }")
        SysLogger("DomainsFactory").warn("BLACKLIST IS DISABLED")

        modules_multimedia = [ "simpledrm", "drm", "snd", "snd_hda_intel", "bluetooth", "btusb", "uvcvideo", "pcspkr", "videobuf2_v4l2", "joydev", "videodev", "videobuf2_common" ]
        modules_usb = [ "sd_mod", "usb_common", "usbcore", "usb_storage" ]
        modules_networking = [ "af_packet", "network", "usbnet", "libphy", "mc", "mii" ]
        blacklisted_modules = [ ]

        if domain_name == "sys-usb":
            pass
            #blacklisted_modules.extend( modules_multimedia )
        elif domain_name == "sys-gui":
            pass
            #blacklisted_modules.extend( modules_usb )
            #blacklisted_modules.extend( modules_networking )
        else:
            pass
            #blacklisted_modules.extend( modules_usb )
            #blacklisted_modules.extend( modules_networking )

        data = [f"blacklist {module}" for module in blacklisted_modules]

        fd, blacklist_conf = tempfile.mkstemp()

        try: 
            os.write(fd, b"\n#Blacklisted by Safecor\n")
            os.write(fd, "\n".join(data).encode())
            os.write(fd, b"\n")
        except Exception as e:
            print(f"Error: Could not write into the temp file {blacklist_conf} : {e}")
            return ""

        return blacklist_conf

###
### Entry point
if __name__ == "__main__":
    SysLogger("DomainsFactory").info("Starting Domains creation process")

    #print("Start topology factory")
    #alpine_repo = sys.argv[1]

    System.get_topology()
    DomainsFactory.create_domains()
