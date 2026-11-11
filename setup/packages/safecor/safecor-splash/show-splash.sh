#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


if grep -qw "nosplash" /proc/cmdline; then
    echo "Splash explicitely disabled on kernel command line"
    exit 0
fi

nohup fbi -d /dev/fb0 -T 1 -noverbose -nointeractive /boot/splash.png  > /dev/null 2>&1 &