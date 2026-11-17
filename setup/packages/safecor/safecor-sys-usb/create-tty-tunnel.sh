#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


DEBUG_ON=$(xenstore-read /local/domain/system/debug_on)

# Verify whether the command worked
if [ $? -ne 0 ]; then 
    echo "Missing debug key in the xenstore. Assuming Debug is off."
    exit 0
fi 

if [ "$DEBUG_ON" = "0" ]; then
    echo "Debug is explicitely disabled. Aborting."
    exit 0
fi 

# Marker identifying the tunnel loop of this device in the process list.
TUNNEL_MARKER="safecor-tty-tunnel $DEVNAME"

# If the device was removed
if [ "$ACTION" = "remove" ]; then 
    echo "Destroying existing tunnel on $DEVNAME"
    pkill -f "$TUNNEL_MARKER" 2>/dev/null
    pkill -f "socat.*$DEVNAME" 2>/dev/null
    exit 0
fi 

# If the device was added
if [ "$ACTION" = "add" ] || [ "$ACTION" = "change" ] ; then 
    echo "Debugging is enabled. Creating a tunnel on serial port $DEVNAME"

    if [ -n "$(pgrep -f "$TUNNEL_MARKER")" ]; then 
        echo "A tunnel already exists for $DEVNAME. Aborting."
        exit 0
    fi

    if [ ! -e "$DEVNAME" ]; then
        echo "The device $DEVNAME does not exist"
        exit 1
    fi

    # Kill a leftover bridge from a previous boot or a crashed tunnel.
    pkill -f "socat.*$DEVNAME" 2>/dev/null

    # Bridge the serial port to the vchan tty client socket in a supervised
    # loop: the socket is created by the setup-vchan service, which starts
    # after the udev events, and may be recreated if the vchan client
    # restarts, so the tunnel must be (re)established automatically.
    LOOP="while true; do
        while [ ! -S /var/run/safecor/tty.sock ]; do sleep 2; done
        socat $DEVNAME,raw,echo=0,b115200 UNIX-CONNECT:/var/run/safecor/tty.sock
        sleep 1
    done"
    setsid sh -c "$LOOP" "$TUNNEL_MARKER" >/dev/null 2>&1 &
fi

exit 0
