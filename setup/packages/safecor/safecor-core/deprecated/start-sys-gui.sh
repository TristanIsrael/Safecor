#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting..."

# Read screen size
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Reading screen size from Xenstore"
screen_size=`xenstore-read /local/domain/system/screen_size`
logger -s -t "Safecor/$SCRIPT_NAME" -p user.debug "Screen size is $screen_size"

# Read screen orientation
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Reading screen rotation from Xenstore"
screen_rotation=`xenstore-read /local/domain/system/screen_rotation`
logger -s -t "Safecor/$SCRIPT_NAME" -p user.debug "Screen rotation is $screen_rotation"

# Compute the resolution with the orientation
normalized_rotation=$(( (screen_rotation % 360 + 360) % 360 ))

# Extract width and height
width=$(echo "$screen_size" | cut -d',' -f1)
height=$(echo "$screen_size" | cut -d',' -f2)

# Calculate new resolution using rotation angle
case $normalized_rotation in
    0|360)
        new_width=$width
        new_height=$height
        ;;
    90|270)
        new_width=$height
        new_height=$width
        ;;
    180)
        new_width=$width
        new_height=$height
        ;;
    *)
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Invalid rotation angle: $screen_rotation"
        exit 1
        ;;
esac

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Start the Domain sys-gui"

umask 007 # With this mask, the sockets will be created with the mode 770
DISPLAY=:0 /usr/sbin/xl create -f /etc/safecor/xen/sys-gui.conf
sleep 1

# Resize GTK window to fill the display
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Resize the GTK window"
DISPLAY=:0 xdotool windowsize `DISPLAY=:0 xdotool search --name "sys-gui"` $new_width $new_height

# We show the splash back
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Show the splash screen"
DISPLAY=:0 feh --fullscreen /boot/splash_fullscreen_rotated.png &

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"