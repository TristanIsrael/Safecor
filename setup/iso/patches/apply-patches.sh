#!/bin/sh

PATCHES_PATH="$1"

echo "Apply patches..."
echo "Patches directory: $1"
echo ""

echo "Applying initramfs patches..."
cd /usr/share/mkinitfs
cp "$1/initramfs-init.patch" .
patch -p0 < initramfs-init.patch

echo ""
echo "Finished applying initramfs patches"
echo ""

echo "Finished applying patches"