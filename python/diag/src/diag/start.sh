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

# Disable the console cursor
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null || true

# Close the splash
echo "exit" > /.splash.ctrl 2>/dev/null || true

# Start the app
/usr/bin/python3 /usr/lib/safecor/diag/src/diag/main.py -platform linuxfb:tty=/dev/null -plugin EvdevKeyboard:$KEYBOARD_EVDEV -plugin EvdevMouse:$MOUSE_EVDEV