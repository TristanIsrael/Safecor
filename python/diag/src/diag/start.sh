#!/bin/sh

# Restart udev
#rc-service udev-trigger restart

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
#exec 3<>/.splash.ctrl
#echo "exit" > /.splash.ctrl 2>/dev/null || true

# Start the app
/usr/bin/python3 /usr/lib/safecor/diag/src/diag/main.py -platform eglfs -plugin EvdevKeyboard:$KEYBOARD_EVDEV -plugin EvdevMouse:$MOUSE_EVDEV