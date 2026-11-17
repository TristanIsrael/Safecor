#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

mkdir -p /var/run/safecor

TTY_SOCK=/var/run/safecor/sys-usb-tty.sock

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Creating TTY tunnel (listen mode)..."
while true; do
    socat PTY,link=/var/run/safecor/tty-admin,raw,echo=0,ctty UNIX-LISTEN:$TTY_SOCK,reuseaddr &
    SOCAT_PID=$!

    # The vchan tty server (group safecor) must be able to connect to the
    # socket: wait for it to appear, then grant the group write access.
    for i in $(seq 1 20); do
        [ -S "$TTY_SOCK" ] && break
        sleep 0.5
    done
    chgrp safecor "$TTY_SOCK" 2>/dev/null || true
    chmod 660 "$TTY_SOCK" 2>/dev/null || true

    wait $SOCAT_PID
    sleep 1
done
