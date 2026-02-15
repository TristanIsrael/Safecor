#!/bin/sh

PATCHES_PATH="$1"

# Apply patch for initramfs-init
cd /usr/share/mkinitfs
cp "$1/initramfs-init.patch" .
patch -p0 < initramfs-init.patch
