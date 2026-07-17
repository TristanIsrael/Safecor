#!/bin/sh

DEBUG_ON=$(xenstore-read /local/domain/system/debug_on)

# Verify whether the command worked
if [ $? -ne 0 ]; then 
    # Missing debug key in the xenstore. Assuming Debug is off.
    logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.notice "Debugging is off. No TTY tunnel will be created"
    exit 0
fi 

if [ "$DEBUG_ON" = "0" ]; then
    # Debug is explicitely disabled. Aborting.
    logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.notice "Debugging is off. No TTY tunnel will be created"
    exit 0
fi 

# If the device was removed
if [ "$ACTION" = "remove" ]; then
    logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.debug "Destroying existing tunnel on $DEVNAME"
    SOCAT_PID=$(pgrep -f "socat.*$DEVNAME")

    if [ $SOCAT_PID -gt 0 ]; then 
        logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.debug "Killing process $SOCAT_PID"
        kill $SOCAT_PID
    fi

    exit 0
fi 

# If the device was added
if [ "$ACTION" = "add" ] || [ "$ACTION" = "change" ] ; then 
    logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.notice "Debugging is enabled. Creating a tunnel on serial port $DEVNAME"

    SOCAT_PID=$(pgrep -f "socat.*$DEVNAME")

    if [ $SOCAT_PID -gt 0 ]; then 
        logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.info "Another tunnel already exists. Aborting."
        exit 0
    fi

    if [ -e "$DEVNAME" ]; then 
        logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.debug "Create TTY tunnel for $DEVNAME"
        socat $DEVNAME,raw,echo=0,b115200 /dev/hvc3,raw,echo=0,b115200 &
    else
        logger -t "Safecor/sys-usb/create-tty-tunnel" -p user.warn "The device $DEVNAME does not exist"
        exit 1
    fi 
fi

exit 0
