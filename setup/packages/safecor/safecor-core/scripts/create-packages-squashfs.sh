#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md

SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Rebuilding packages.squashfs..."

cd /usr/lib/safecor
mksquashfs packages packages.squashfs -comp zstd -Xcompression-level 1 -b 128K -noappend -no-xattrs

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "packages.squashfs rebuilt successfully"
