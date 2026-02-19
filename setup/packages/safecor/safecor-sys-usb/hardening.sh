#!/bin/bash

# This file contains kernel parameters and shell instructions to harden 
# the sys-usb domain

echo "Apply hardening"

# Unload unnecessary drivers
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

echo "Hardening finished"