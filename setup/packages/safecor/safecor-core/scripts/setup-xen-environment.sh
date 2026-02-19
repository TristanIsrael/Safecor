#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

. /etc/safecor/constants.sh

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Setup XEN environment"

# Setup the replacement script for qemu-system to patch the command
# line sent by XEN
# Setup QEMU proxy for XEN display
# TODO: replace with an alias
if [ ! -L /usr/bin/qemu-system-x86_64 ]; then
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Patch QEMU command line..."
    mv /usr/bin/qemu-system-x86_64 /usr/bin/qemu-system-x86_64.real
    ln -s /usr/bin/qemu-system-x86_64.cmd /usr/bin/qemu-system-x86_64
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"
else
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "QEMU is already patched"
fi

CONFIG_REPO=`jq -r '.network.repository' /etc/safecor/topology.json`
CONFIG_RELEASES=`jq -r '.network.releases' /etc/safecor/topology.json`

if grep -q "PANOPTISCAN_CONFIG=nomade" "/proc/cmdline"; then
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "(Nomade) Verify Alpine ISO image"
    if [ -f $ALPINE_VIRT_ISO_LOCAL ]
    then 
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "ISO image is ready"
    else 
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "ISO image not found, aborting"
        exit 1
    fi
else
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Verify Alpine virt ISO image"
    rm -rf /var/lib/xen/boot
    rm -rf /usr/lib/safecor/tmp/alpine-virt

    if [ -f $ALPINE_VIRT_ISO_LOCAL ]
    then 
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Alpine virt ISO image is PRESENT"
    else
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "... Alpine virt ISO image is MISSING"
        exit 1
    fi
    
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Extract boot files (kernel, initrd)"    
    mkdir -p /var/lib/xen/boot
    mkdir -p /usr/lib/safecor/tmp/alpine-virt
    modprobe iso9660
    mount -o loop $ALPINE_VIRT_ISO_LOCAL /media/cdrom
    cp /media/cdrom/boot/vmlinuz-* /var/lib/xen/boot
    cp /media/cdrom/boot/modloop-* /var/lib/xen/boot
    cp /media/cdrom/boot/initramfs-* /var/lib/xen/boot
    umount /media/cdrom

    if [ -f $ALPINE_LTS_ISO_LOCAL ]
    then 
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Alpine standard ISO image is PRESENT"
    else
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "... Alpine standard ISO image is MISSING"
        exit 1   
    fi

    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... Extract boot files (kernel, initrd)"    
    mkdir -p /var/lib/xen/boot
    mkdir -p /usr/lib/safecor/tmp/alpine-standard
    modprobe iso9660
    mount -o loop $ALPINE_LTS_ISO_LOCAL /media/cdrom
    cp /media/cdrom/boot/vmlinuz-* /var/lib/xen/boot
    cp /media/cdrom/boot/modloop-* /var/lib/xen/boot
    cp /media/cdrom/boot/initramfs-* /var/lib/xen/boot
    umount /media/cdrom    
fi

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"