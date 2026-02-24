#!/bin/sh

echo "**** Set mouse pointer ****"
xsetroot -display :0 -cursor_name left_ptr

echo "**** Setting graphical mode"

# Read screen size
#domid=`xenstore-read domid`
screen_size=`xenstore-read /local/domain/system/screen_size`

# Read screen orientation
screen_rotation=`xenstore-read /local/domain/system/screen_rotation`

# Compute the resolution with the orientation
normalized_rotation=$(( (screen_rotation % 360 + 360) % 360 ))

# Extraction de la largeur et de la hauteur
width=$(echo "$screen_size" | cut -d',' -f1)
height=$(echo "$screen_size" | cut -d',' -f2)

# Calcul de la nouvelle résolution en fonction de la rotation
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
        echo "Rotation invalide : $screen_rotation"
        exit 1
        ;;
esac

# Apply the resolution
resolution="$new_width"x"$new_height"
xrandr --output Virtual-1 --display :0 --mode $resolution
