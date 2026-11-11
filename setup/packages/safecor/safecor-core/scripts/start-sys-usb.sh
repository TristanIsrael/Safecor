#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting Domain sys-usb"

umask 007 # With this mask, the sockets will be created with the mode 770
/usr/sbin/xl create -f /etc/safecor/xen/sys-usb.conf
sleep 1

# Write the domid to xenstore for other domains to discover
domid=$(xl info sys-usb | grep -w ID | awk '{print $3}')
if [ -n "$domid" ]; then
    xenstore-write /local/domain/system/domids/sys-usb "$domid"
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.debug "sys-usb domid $domid written to xenstore"
else
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Failed to get domid for sys-usb"
fi

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"