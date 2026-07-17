#!/bin/sh

host=$(hostname)

logger -t "Safecor/$host/safecor-gui-base" -p user.notice "Configure the X server"

xset -display :0 -dpms
xset -display :0 s off

logger -t "Safecor/$host/safecor-gui-base" -p user.info "**** Set the mouse pointer ****"
xsetroot -display :0 -cursor_name left_ptr
# Hide the mouse cursor when inactive
unclutter-xfixes -idle 1 -root -noevents &

logger -t "Safecor/$host/safecor-gui-base" -p user.info "**** Set the graphical mode"

# Read screen size
screen_size=`xenstore-read /local/domain/system/screen_size`

# Read screen orientation
screen_rotation=`xenstore-read /local/domain/system/screen_rotation`

# Compute the resolution with the orientation
normalized_rotation=$(( (screen_rotation % 360 + 360) % 360 ))

# Extraction de la largeur et de la hauteur
width=$(echo "$screen_size" | cut -d',' -f1)
height=$(echo "$screen_size" | cut -d',' -f2)

# Compute the new resolution depending on the rotation
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
        logger -t "Safecor/$host/safecor-gui-base" -p user.warn "Invalid rotation: $screen_rotation"
        exit 1
        ;;
esac

# Apply the resolution
resolution="$new_width"x"$new_height"
logger -t "Safecor/$host/safecor-gui-base" -p user.info "Apply the resolution $new_width x $new_height"
xrandr --output Virtual-1 --display :0 --mode $resolution
