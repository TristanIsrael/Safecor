#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


/usr/sbin/xl list | grep "^sys-gui" | awk '{print $2}'

return 0