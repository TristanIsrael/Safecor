#!/bin/sh

logger -s -t "Safecor/core" -p user.notice "Create a TTY tunnel"

logger -s -t "Safecor/core" -p user.info "Waiting for the socket sys-usb-tty.sock..."
while [ ! -e "/var/run/safecor/sys-usb-tty.sock" ]; do
    sleep 1
done

logger -s -t "Safecor/core" -p user.info "The socket sys-usb-tty-sock is ready"

logger -s -t "Safecor/core" -p user.info "Creating a tunnel between the socket sys-usb-tty-sock and the device tty-admin..."
#socat UNIX-CONNECT:/var/run/safecor/sys-usb-tty.sock PTY,link=/var/run/safecor/tty-admin,raw,echo=0,ctty
while true; do
    socat PTY,link=/var/run/safecor/tty-admin,raw,echo=0,waitslave UNIX-CONNECT:/var/run/safecor/sys-usb-tty.sock
    sleep 1
done
logger -s -t "Safecor/core" -p user.info "... the tunnel is now closed"