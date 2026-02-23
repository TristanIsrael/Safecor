#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for the device tty-admin..."
while [ ! -e "/var/run/safecor/tty-admin" ]; do
    sleep 1
done

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... device tty-admin found"

while true; do
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for a new session on tty-admin..."
    setsid getty -L 115200 /var/run/safecor/tty-admin vt100
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... session terminated on tty-admin"
done