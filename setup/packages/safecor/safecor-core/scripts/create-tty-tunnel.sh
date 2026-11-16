#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

mkdir -p /var/run/safecor

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Creating TTY tunnel (listen mode)..."
while true; do
    socat PTY,link=/var/run/safecor/tty-admin,raw,echo=0,ctty UNIX-LISTEN:/var/run/safecor/sys-usb-tty.sock,reuseaddr
    sleep 1
done
