#!/bin/bash

# This file contains kernel parameters and shell instructions to harden 
# the sys-usb domain

logger -t "Safecor/sys-usb/hardening" -p user.notice "Apply hardening"

# Unload unnecessary drivers
logger -t "Safecor/sys-usb/hardening" -p user.info "Remove unnecessary kernel modules"
modprobe -r af_packet 
modprobe -r virtio_net 
modprobe -r net_failover
modprobe -r floppy
modprobe -r simpledrm
modprobe -r simpledrm
modprobe -r drm_shmem_helper

# Disable module loading after this point
sysctl -w kernel.modules_disabled=1

debug=$(xenstore-read /local/domain/system/debug_on)

if [ "$debug" != "1" ]; then
    # Disable root connection
    truncate -s 0 /etc/securetty
    pwd=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 256)
    echo "root:$pwd" | chpasswd
fi

logger -t "Safecor/sys-usb/hardening" -p user.notice "Hardening finished"