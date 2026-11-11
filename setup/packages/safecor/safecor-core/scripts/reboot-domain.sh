#!/bin/sh

SCRIPT_NAME=$(basename "$0")

/usr/sbin/xl reboot "$1"
sleep 3

# After reboot the domain has a new domid, update xenstore
domid=$(xl info "$1" | grep -w ID | awk '{print $3}')
if [ -n "$domid" ]; then
    xenstore-write /local/domain/system/domids/$1 "$domid"
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.debug "Domain $1 new domid $domid written to xenstore"
else
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Failed to get domid for $1 after reboot"
fi
