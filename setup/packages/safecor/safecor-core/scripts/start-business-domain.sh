#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting Domain $1..."

umask 007 # With this mask, the sockets will be created with the mode 770
/usr/sbin/xl create -f /etc/safecor/xen/$1.conf

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"
