# sys-usb controller

> **Scope**: the USB controller domain — USB storage management, file API over disks, inputs daemon, debug TTY.
>
> **Last updated**: 2026-11-20
>
> **Main artifacts**: `SysUsbController` (`_sys_usb_controller.py`), the `safecor-sys-usb` package (post-install, `hardening.sh`), `create-tty-tunnel.sh`, `create-tty-terminal.sh`.

`sys-usb` is a **core DomU** with low trust: it is the only domain that sees the physical USB buses (PCI passthrough) and it is the only domain that can read/write external storage. Every other domain accesses disks through its file API (MQTT) or through the direct USB mount (see [direct-usb-mount.md](direct-usb-mount.md)).

## Responsibilities

- **USB storage management**: USB disks are mounted under `/media/usb/<label>`; archives (`.iso`, `.zip`, `.tar`, ...) can be mounted as virtual disks (`mount_file` / `unmount`).
- **File API over disks**: answers `list_disks`, `list_files`, `read_file` (stages into the repository), `copy_file`, `create_file`, `file_fingerprint` (md5), `delete_file`. See [../../development/protocol.md](../../development/protocol.md) for the payloads.
- **Inputs daemon**: reads the evdev events of the physical keyboard/mouse/touch and forwards them over the vchan `input` channel (see [inputs.md](inputs.md)).
- **Direct mount server side**: for each authorized domain, the SFTP server over the vchan `sftp` channel (see [direct-usb-mount.md](direct-usb-mount.md)).
- **Queue management**: `system/sys-usb/clear-queues` clears the pending commands.

## Hardening

`hardening.sh` (package `safecor-sys-usb`) applies the hardening rules: unprivileged service users, `safecor` group ownership, and reads `debug_on` from xenstore to enable or disable the debug TTY bridge. See [../../security/security-model.md](../../security/security-model.md).

## Debug TTY chain

With `DEBUG=ON` on the Dom0 kernel command line (started by `debug.initd`), the USB serial console cable is passed through to `sys-usb` and bridged to a Dom0 getty:

```
host debug terminal → USB cable → sys-usb /dev/ttyUSB0 (udev rule 99-usbserial.rules)
  → socat (create-tty-tunnel.sh, supervised loop) → /var/run/safecor/tty.sock (vchan client)
  → vchan "tty" channel → vchan-socket-proxy server (Dom0)
  → /var/run/safecor/sys-usb-tty.sock (Dom0) → socat (debug.initd, PTY mode)
  → /var/run/safecor/tty-admin → getty (create-tty-terminal.sh) → Dom0 login
```

## Testing

The emulator's `MockSysUsbController` stands in for this domain: it answers the same MQTT commands operating on local directories. See [../../development/testing.md](../../development/testing.md).
