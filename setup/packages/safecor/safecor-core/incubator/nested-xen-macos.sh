#!/usr/bin/env bash
# Installation : ./xen-qemu.sh alpine-standard-aarch64.iso
# Démarrage    : ./xen-qemu.sh
set -euo pipefail

ISO="${1:-}"
DISK="bin.nosync/xen-test.qcow2"
VARS="bin.nosync/xen-uefi-vars.fd"
FW="$(brew --prefix qemu)/share/qemu/edk2-aarch64-code.fd"

mkdir -p bin.nosync

[ -f "$DISK" ] || qemu-img create -f qcow2 "$DISK" 20G
[ -f "$VARS" ] || truncate -s 64m "$VARS"

#-cpu max,pauth-impdef=on
#-nographic

ARGS=(
  -accel hvf
  -machine virt,virtualization=on,gic-version=3
  -cpu max
  -smp 4 -m 4096
  -boot menu=on,splash-time=0
  -drive if=pflash,format=raw,readonly=on,file="$FW"
  -drive if=pflash,format=raw,file="$VARS"
  -drive if=none,id=hd0,format=qcow2,file="$DISK"
  -device virtio-blk-pci,drive=hd0,bootindex=2
  -nic user,model=virtio-net-pci,dns=1.1.1.1  
  -device nec-usb-xhci,id=xhci
  -device usb-kbd,bus=xhci.0
  -device usb-tablet,bus=xhci.0
  -device virtio-gpu-pci
  -display none
  -serial stdio
  -monitor none
)

if [ -n "$ISO" ]; then
  ARGS+=(
    -device virtio-scsi-pci,id=scsi0
    -drive if=none,id=cd0,media=cdrom,readonly=on,file="$ISO"
    -device scsi-cd,drive=cd0,bus=scsi0.0,bootindex=1
  )
fi

exec qemu-system-aarch64 "${ARGS[@]}"