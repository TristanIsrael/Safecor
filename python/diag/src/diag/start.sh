#!/bin/sh

# Restart udev
rc-service udev-trigger restart

# Look for the keyboard
KEYBOARD=$(find /dev/input/by-path/ -type l -name '*-kbd' | head -n1)

# Look for the mouse
MOUSE=$(find /dev/input/by-path/ -type l -name '*-mouse' | head -n1)

# Resolve symbolic links from /dev/input/eventX
KEYBOARD_EVDEV=$(readlink -f "$KEYBOARD")
MOUSE_EVDEV=$(readlink -f "$MOUSE")

# Affichage de debug
echo "Detected keyboard at: $KEYBOARD_EVDEV"
echo "Detected mouse at: $MOUSE_EVDEV"

# Close the splash
echo "exit" > /.splash.ctrl

/usr/bin/python3 /usr/lib/safecor/diag/src/diag/main.py -platform linuxfb -plugin EvdevKeyboard:$KEYBOARD_EVDEV -plugin EvdevMouse:$MOUSE_EVDEV