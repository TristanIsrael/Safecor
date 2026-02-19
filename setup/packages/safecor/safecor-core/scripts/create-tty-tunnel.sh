#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for the socket sys-usb-tty.sock..."
while [ ! -e "/var/run/sys-usb-tty.sock" ]; do
    sleep 1
done

logger -t "Safecor/$SCRIPT_NAME" -p user.info "The socket sys-usb-tty-sock is ready"

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Creating a tunnel between the socket sys-usb-tty-sock and the device tty-admin..."
socat UNIX-CONNECT:/var/run/sys-usb-tty.sock PTY,link=/dev/tty-admin,raw,echo=0,ctty
logger -t "Safecor/$SCRIPT_NAME" -p user.info "... the tunnel is now closed"