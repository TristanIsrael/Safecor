#!/bin/sh

set -e
logger -s -t "Safecor/core" -p user.info "Starting the Domain sys-usb"

umask 007 # With this mask, the sockets will be created with the mode 770
/usr/sbin/xl create -f /etc/safecor/xen/sys-usb.conf
sleep 1

logger -s -t "Safecor/core" -p user.info "The Domain sys-usb is starting"