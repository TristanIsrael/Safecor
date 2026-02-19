#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting Domain sys-usb"

xl create -f /etc/safecor/xen/sys-usb.conf

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Set permissions on PV sockets"
sleep 1

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"