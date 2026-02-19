#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting Domain $1..."

xl create -f /etc/safecor/xen/$1.conf

logger -t "Safecor/$SCRIPT_NAME" -p user.info "... done"
