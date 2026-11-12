# safecor-sys-usb

## Boot sequence

- DomU is started in **PVH** mode using the Dom0 kernel (`/boot/vmlinuz-lts`)
- The rootfs is the shared `alpine-virt.iso` mounted as a read-only block device
- The APK Overlay is loaded from the config disk (`/dev/sdd`)
- Packages repository is mounted from `/etc/fstab`
- Needed packages are installed