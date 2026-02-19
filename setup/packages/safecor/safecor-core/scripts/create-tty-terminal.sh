#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for the device tty-admin..."
while [ ! -e "/dev/tty-admin" ]; do
    sleep 1
done

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... device tty-admin found"

while true; do
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for a new session on tty-admin..."
    setsid agetty -h -t 60 -L 115200 tty-admin vt100
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... session terminated on tty-admin"
done