#!/bin/sh

logger -s -t "Safecor/core" -p user.notice "Create a TTY terminal..."

logger -s -t "Safecor/core" -p user.info "Waiting for the device tty-admin..."
while [ ! -e "/var/run/safecor/tty-admin" ]; do
    sleep 1
done

logger -s -t "Safecor/core" -p user.info "... device tty-admin found"

while true; do
    logger -s -t "Safecor/core" -p user.info "Waiting for a new session on tty-admin..."
    setsid /sbin/getty -L 115200 /var/run/safecor/tty-admin vt100
    logger -s -t "Safecor/core" -p user.info "... session terminated on tty-admin"
done