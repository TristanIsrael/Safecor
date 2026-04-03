#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Starting Domain $1..."

IS_GUI=$2

# We need to know whether this Domain has a graphical interface and set different
# settings and manage its position
# The information is given by the caller as the first argument
if [ -z "$IS_GUI" ] || [ "$IS_GUI" == 0 ]; then
    # This is not a GUI Domain
    IS_GUI=0
else 
    # This is a GUI Domain

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

    # Start the domain
    umask 007
    DISPLAY=:0 /usr/sbin/xl create -f /etc/safecor/xen/$1.conf
    sleep 1

    # Verify whether the Domain has focus
    FOCUS_DOMAIN=$(xenstore-read /local/domain/system/input-focus)

    if [ "$FOCUS_DOMAIN" = "$1" ]; then
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Giving the focus to this Domain"
        DISPLAY=:0 xdotool windowsize `DISPLAY=:0 xdotool search --name "$1"` $new_width $new_height
    else 
        logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "This Domain does not have the focus, hiding the window"
        DISPLAY=:0 xdotool windowunmap `DISPLAY=:0 xdotool search --name "$1"`
    fi

    exit 0

fi

umask 007 # With this mask, the sockets will be created with the mode 770
/usr/sbin/xl create -f /etc/safecor/xen/$1.conf