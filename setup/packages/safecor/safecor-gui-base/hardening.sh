#!/bin/bash
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


# This file contains kernel parameters and shell instructions to harden 
# the GUI domain

echo "Apply hardening"

# Unload network drivers
modprobe -r af_packet 
modprobe -r virtio_net 
modprobe -r net_failover
modprobe -r psmouse
modprobe -r mousedev
modprobe -r evdev
modprobe -r floppy
modprobe -r button
modprobe -r tiny_power_button
modprobe -r usb_storage
modprobe -r usbcore
modprobe -r usb_commpon
modprobe -r usb_common
modprobe -r sd_mod

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