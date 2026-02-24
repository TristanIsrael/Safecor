#!/bin/sh

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

# If the device was removed
if [ "$ACTION" = "remove" ]; then 
    echo "Destroying existing tunnel on $DEVNAME"
    SOCAT_PID=$(pgrep -f "socat.*$DEVNAME")

    if [ $SOCAT_PID -gt 0 ]; then 
        echo "Killing process $SOCAT_PID"
        kill $SOCAT_PID
    fi

    exit 0
fi 

# If the device was added
if [ "$ACTION" = "add" ] || [ "$ACTION" = "change" ] ; then 
    echo "Debugging is enabled. Creating a tunnel on serial port $DEVNAME"

    SOCAT_PID=$(pgrep -f "socat.*$DEVNAME")

    if [ $SOCAT_PID -gt 0 ]; then 
        echo "Another tunnel already exists. Aborting."
        exit 0
    fi

    if [ -e "$DEVNAME" ]; then 
        echo Create TTY tunnel for "$DEVNAME"
        socat $DEVNAME,raw,echo=0 /dev/hvc3,raw,echo=0 &        
    else
        echo "The device $DEVNAME does not exist"
        exit 1
    fi 
fi

exit 0
