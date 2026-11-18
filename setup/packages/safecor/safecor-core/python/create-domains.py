"""Creates all DomU Xen domains from the topology definition during system setup.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import subprocess
import tempfile

from safecor import Domain, DomainType, SysLogger, System

DEFAULT_SAFECOR_VIRT_ISO_FILEPATH = "/var/lib/xen/images/alpine-virt.iso"


class DomainsFactory:
    """This class is designed to orchestrate the Domains creation during the
    setup process of a system based on Safecor.

    The Domains are defined in the file /etc/safecor/topology.json.
    """

    @staticmethod
    def create_domains():
        """Creates all the Domains of a Safecor system"""

        SysLogger("create-domains").info("Start creating domains from topology")

        topology = System.get_topology()

        if topology.use_usb:
            blacklist_conf = DomainsFactory.__create_blacklist_conf("sys-usb")
            DomainsFactory.__provision_domain(
                "sys-usb", "safecor-sys-usb", "virt", blacklist_conf
            )
            DomainsFactory.__create_domd_usb()

        DomainsFactory.__create_business_domains()
        DomainsFactory.create_packages_squashfs()

        SysLogger("create-domains").info("Finished creating domains")

    ###
    # Private functions
    #
    @staticmethod
    def __create_domd_usb():
        "Creates the Xen configuration file for the sys-usb Driver Domain."
        SysLogger("create-domains").info(
            "Create configuration for Driver Domain sys-usb"
        )

        conf = DomainsFactory.__create_xl_conf_sys_usb()

        if conf is not None:
            filename = "/etc/safecor/xen/sys-usb.conf"
            with open(filename, "w") as f:
                f.write(conf)

            try:
                os.chmod(filename, 0o770)
            except Exception as e:
                SysLogger("create-domains").info(
                    f"Could not set permission on file {filename} : {e}"
                )

        SysLogger("create-domains").info(
            "Configuration for Domain sys-usb created successfully"
        )

    @staticmethod
    def __create_business_domains():
        "Creates Xen configuration files and provisions Alpine packages for all business Domains."
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
                DomainsFactory.__provision_domain(
                    domain.name,
                    package,
                    "virt",
                    blacklist_conf,
                    is_hvm=domain.has_gui,
                )
                conf = DomainsFactory.__create_xl_conf_domain(
                    domain,
                    boot_iso_location=f"bootiso-{domain.name}.iso",
                )

                filename = f"/etc/safecor/xen/{domain.name}.conf"
                with open(filename, "w") as f:
                    f.write(conf)

                try:
                    os.chmod(filename, 0o770)
                except Exception as e:
                    SysLogger("create-domains").info(
                        f"Could not set permission on file {filename} : {e}"
                    )

                DomainsFactory.__fetch_alpine_packages(package)

                SysLogger("create-domains").info(
                    f"Domain {domain.name} created successfully"
                )
        else:
            SysLogger("create-domains").info("There are not business domains to create")

    @staticmethod
    def __create_xl_conf_sys_usb() -> None:
        "Generates the xl configuration string for the sys-usb Domain (PVH)."
        topology = System.get_topology()

        sys_usb = topology.domain("sys-usb")

        txt = f'''
type = "pv"
name = "sys-usb"
serial = "pty" 
memory = {sys_usb.memory}
vcpus = {sys_usb.vcpus}
cpus = "{System.cpu_affinity_to_string(sys_usb.cpu_affinity)}"
kernel = "/var/lib/xen/boot/vmlinuz-safecor-virt"
ramdisk = "/var/lib/xen/boot/initramfs-safecor-virt"
modloop = "/var/lib/xen/boot/modloop-safecor-virt"
driver_domain = 1
extra = "console=hvc0 alpine_dev=xvdc:iso9660 apkovl=/media/xvdd/sys-usb.apkovl.tar.gz modules=loop,squashfs,ext4,xen_blkfront,sd-mod,usb-storage"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=xvdd, access=r, target=/usr/lib/safecor/system/sys-usb-config.img',
    'format=raw, vdev=xvde, access=r, target=/usr/lib/safecor/packages.squashfs'
]
vif=[]
'''

        return txt

    @staticmethod
    @DeprecationWarning
    def __create_xl_conf_sys_gui() -> None:
        "Generates the xl configuration string for the sys-gui Domain."
        topology = System.get_topology()

        sys_gui = topology.domain("sys-gui")

        txt = f'''
type = "hvm"
name = "sys-gui"
serial = "pty" 
memory={sys_gui.memory}
vcpus = {sys_gui.vcpus}
cpus = "{System.cpu_affinity_to_string(sys_gui.cpu_affinity)}"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=xvdd, access=r, target=/usr/lib/safecor/system/sys-gui-config.img'
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
    def __create_xl_conf_domain(
        domain: Domain,
        boot_iso_location: str,
    ):
        "Generates the xl configuration string for a generic Domain."
        topology = System.get_topology()

        dom = topology.domain(domain.name)

        if domain.has_gui:
            return DomainsFactory.__create_xl_conf_hvm(domain, boot_iso_location)
        else:
            return DomainsFactory.__create_xl_conf_pvh(domain, boot_iso_location)

    @staticmethod
    def __create_xl_conf_pvh(
        domain: Domain,
        boot_iso_location: str,
    ):
        "Generates the PVH xl configuration for a non-GUI Domain."
        dom = System.get_topology().domain(domain.name)

        txt = f'''
type = "pvh"
serial = "pty"
name = "{domain.name}"
memory = {domain.memory}
vcpus = {domain.vcpus}
cpus = "{System.cpu_affinity_to_string(dom.cpu_affinity)}"
kernel = "/var/lib/xen/boot/vmlinuz-safecor-virt"
ramdisk = "/var/lib/xen/boot/initramfs-safecor-virt"
modloop = "/var/lib/xen/boot/modloop-safecor-virt"
extra = "console=hvc0 alpine_dev=xvdc:iso9660 apkovl=/media/xvdd/{domain.name}.apkovl.tar.gz modules=loop,squashfs,ext4,xen_blkfront"
disk = [
	'format=raw, vdev=xvdc, access=r, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=xvdd, access=r, target=/usr/lib/safecor/system/{domain.name}-config.img',
    'format=raw, vdev=xvde, access=r, target=/usr/lib/safecor/packages.squashfs'
'''
        if domain.temp_disk_size > 0:
            txt += f", 'format=raw, vdev=xvdg, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-tmp.img'"

        if domain.swap_size > 0:
            txt += f", 'format=raw, vdev=xvdf, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-swap.img'"

        txt += """
]
vif=[]
"""

        return txt

    @staticmethod
    def __create_xl_conf_hvm(
        domain: Domain,
        boot_iso_location: str,
    ):
        "Generates the HVM xl configuration for a GUI Domain."
        dom = System.get_topology().domain(domain.name)

        txt = f'''
type = "hvm"
serial = "pty" 
boot = "d"
name = "{domain.name}"
memory = {domain.memory}
vcpus = {domain.vcpus}
cpus = "{System.cpu_affinity_to_string(dom.cpu_affinity)}"
disk = [
	'format=raw, vdev=xvdc, access=r, devtype=cdrom, target={DEFAULT_SAFECOR_VIRT_ISO_FILEPATH}',
    'format=raw, vdev=sdd, access=r, devtype=cdrom, target=/usr/lib/safecor/system/{domain.name}-config.img',
    'format=raw, vdev=sde, access=r, target=/usr/lib/safecor/packages.squashfs'
'''
        if domain.temp_disk_size > 0:
            txt += f", 'format=raw, vdev=sdg, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-tmp.img'"

        if domain.swap_size > 0:
            txt += f", 'format=raw, vdev=sdf, access=rw, target=/usr/lib/safecor/tmp/{domain.name}-swap.img'"

        txt += f"""
]
device_model_override = "/usr/bin/qemu-system-x86_64"
device_model_version = "qemu-xen"
device_model_args = [
      #'-device', 'virtio-gpu-pci',
      '-display', 'gtk,full-screen=on,zoom-to-fit=on',
      '-device', 'virtio-input-host,id=virtio-mouse,evdev=/var/run/safecor/virtual_mouse_{domain.name}',
      '-device', 'virtio-input-host,id=virtio-keyboard,evdev=/var/run/safecor/virtual_keyboard_{domain.name}',
      '-device', 'virtio-input-host,id=virtio-touch,evdev=/var/run/safecor/virtual_touch_{domain.name}'
]
vga = "stdvga"
vnc=0
usb=0
vif=[]
"""

        return txt

    @staticmethod
    def __provision_domain(
        domain_name: str,
        main_package: str,
        alpine_branch: str = "virt",
        blacklist_conf: str = None,
        is_hvm: bool = False,
    ):
        "Provisions a Domain by creating its boot ISO from the Alpine repository."
        cmd = "/usr/lib/safecor/bin/provision-domain.sh"
        args = [cmd, domain_name, main_package, alpine_branch, blacklist_conf]
        if is_hvm:
            args.append("hvm")

        try:
            subprocess.run(args, check=True)

            # When finished we remove the blacklist.conf file
            os.unlink(blacklist_conf)
        except Exception as e:
            SysLogger("create-domains").error(
                f"An error occured during the provisioning of the domain {domain_name}"
            )
            SysLogger("create-domains").error(e)

    @staticmethod
    def __fetch_alpine_packages(package):
        "Downloads Alpine packages required by a Domain into the local repository."
        # Fetch Alpine packages
        if package is None:
            SysLogger("create-domains").error("No package name provided")
            return

        subprocess.run(
            args=["apk", "fetch", "-R", package],
            cwd="/usr/lib/safecor/packages/alpine/x86_64",
            check=True,
        )

        subprocess.run(
            args=["/usr/lib/safecor/bin/reindex-and-sign-repository.sh"], check=True
        )

    ###
    ### Private functions
    @staticmethod
    def create_packages_squashfs():
        """Creates the packages.squashfs image from the local Alpine repository.

        The resulting file is placed at /usr/lib/safecor/packages.squashfs,
        matching the xvde disk target in the generated XL configs.
        """
        SysLogger("create-domains").info("Creating packages.squashfs")
        subprocess.run(
            args=[
                "mksquashfs",
                "packages",
                "packages.squashfs",
                "-comp",
                "zstd",
                "-Xcompression-level",
                "1",
                "-b",
                "128K",
                "-noappend",
                "-no-xattrs",
            ],
            cwd="/usr/lib/safecor",
            check=True,
        )
        SysLogger("create-domains").info("packages.squashfs built successfully")

    @staticmethod
    def __create_blacklist_conf(domain_name: str = "") -> str:
        "Generates the PCI device blacklist configuration from the topology."
        SysLogger("DomainsFactory").info(
            f"Create blacklist.conf file for {domain_name if domain_name != '' else 'standard Domain'}"
        )
        SysLogger("DomainsFactory").warn("BLACKLIST IS DISABLED")

        modules_multimedia = [
            "simpledrm",
            "drm",
            "snd",
            "snd_hda_intel",
            "bluetooth",
            "btusb",
            "uvcvideo",
            "pcspkr",
            "videobuf2_v4l2",
            "joydev",
            "videodev",
            "videobuf2_common",
        ]
        modules_usb = ["sd_mod", "usb_common", "usbcore", "usb_storage"]
        modules_networking = ["af_packet", "network", "usbnet", "libphy", "mc", "mii"]
        blacklisted_modules = []

        if domain_name == "sys-usb" or domain_name == "sys-gui":
            pass
            # blacklisted_modules.extend( modules_usb )
            # blacklisted_modules.extend( modules_networking )
        else:
            pass
            # blacklisted_modules.extend( modules_usb )
            # blacklisted_modules.extend( modules_networking )

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

    # print("Start topology factory")
    # alpine_repo = sys.argv[1]

    System.get_topology()
    DomainsFactory.create_domains()
