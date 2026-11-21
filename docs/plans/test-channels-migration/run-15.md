# Run 15

Purpose: final validation run of the channels → vchan migration (#256) — validate the #260 fix (the sshfs direct mount: the sftp-server chroot built at boot, the socat→proxy startup order, the `-R`/`-u 077` flags, the `reconnect` sshfs option), the #262 fix (the domid write race in `reboot-domain.sh`), re-validate the debug tty (the run-14 regression — Phase D) and the five objectives of `test-channels-migration.md`.

Preparation:
- [x] Implement Phase C (#262: `reboot-domain.sh` polls for the domain to go down, then for it to come back with a new domid, and only then writes the new domid to xenstore)
- [x] Rebuild the packages changed since run 14 from `version-2`:
  - `safecor-lib` (the `reconnect` sshfs option in `DirectMountManager`)
  - `safecor-sys-usb` (the `safecor-vchan-sftp.py` rewrite)
  - `safecor-core` (the `reboot-domain.sh` polling fix)
- [x] On Dom0: `apk update && apk add safecor-core` (and the rebuilt packages on the DomUs at reprovisioning)
- [x] Full cold boot in debug mode with a USB disk connected before boot

Verification — #260, the sshfs direct mount:
- [ ] On sys-usb, the sftp chroot is built at boot: `ls -l /media/usb/usr/lib/ssh/` contains `sftp-server`, the shared libraries and `/lib64/ld-linux-x86-64.so.2`
- [ ] On sys-usb, for each direct_mount domain: one `socat UNIX-LISTEN:/var/run/safecor/vchan-<name>.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/vchan-<name>.sock` (the socat started before the proxy)
- [ ] The `ro` domains get `sftp-server -u 077 -R`, the `rw` domains `-u 077` only
- [ ] On a business domain with `direct_mount`, `/media/usb` is mounted automatically at boot (`mount | grep /media/usb`)
- [ ] The sshfs options include `reconnect` (`cat /proc/$(pidof sshfs)/cmdline`)
- [ ] A file from the USB disk connected before boot is readable through the mount: `cat /media/usb/<disk>/<file>`
- [ ] `rw` domain: a file written through the mount is visible on the USB disk (and vice versa)
- [ ] `ro` domain: a write through the mount is refused
- [ ] USB hot-plug: connect a second USB disk after boot, it appears in the `/media/usb` mount of the business domains without reboot

Verification — #262, the vchans after an API reboot (requires the Phase C fix):
- [ ] After the reboot, `/local/domain/system/domids/<name>` holds the new domid (written only once the domain is Running again)
- [ ] `system/workflow/restart_domain/request` on sys-usb: all the vchans come back (the `msg` channel of every domain, the `input`/`tty`/`sftp` channels of sys-usb) — the Dom0 discovery loop recreates the servers with the new domid
- [ ] `system/workflow/restart_domain/request` on a business domain: its `msg` channel and its `sftp` channel (if `direct_mount`) come back, and its `/media/usb` mount heals (the `reconnect` option)

Verification — Phase D, the debug tty regression (run 14):
- [ ] Diagnose the chain: which process/socket of (Dom0: `vchan-socket-proxy -m server` for the tty channel → `create-tty-tunnel.sh` → `create-tty-terminal.sh` → `getty` on `/var/run/safecor/tty-admin`) / (sys-usb: the `tty` vchan client → `socat /dev/ttyUSB0`) is dead, and why (service ordering after the run-13→14 changes)
- [ ] Fix it (dedicated commit, no issue — user decision)
- [ ] The debug tty works in debug mode (type on the USB serial terminal, it appears on the Dom0 console)

Verification — the five objectives (test-channels-migration.md) + regressions:
- [ ] Messaging on all domains (the local brokers, the `msg` vchan bridge, client IDs `safecor-<domain>-bridge` on Dom0)
- [ ] Inputs on sys-usb (mouse/touch)
- [ ] GUI display (the GUI domain displays, the Saphir app starts, its messages are visible on the bus)
- [ ] The local brokers stay connected across the reboots tested above

If everything is green: close #256 (and #258, #264, #260, #262 as validated), update `docs/project-status.md`, check the objectives in `test-channels-migration.md`, and move to the second pass (Phase F: #259, #261).

## Run 15 resolutions

Run 15 validated the `reconnect` sshfs option but the #260 fix was not working: the sftp-server chroot built at boot was empty (musl `ldd` output not parsed), so every sftp session died instantly and the FUSE mount was stuck. The chroot approach was replaced by a per-session bubblewrap sandbox.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | The sftp chroot built at boot is empty (`/media/usb/usr/lib/ssh/` only contains `sftp-server`, no dynamic linker or libraries): `parse_ldd` parsed the glibc `ldd` format, incompatible with Alpine/musl, so the chrooted sftp-server could not exec. Every sftp session died instantly (zombie `[sftp-server]` processes), the FUSE mount was dead but present (`df` stuck, files unreadable). | Decision: drop the boot-time chroot, switch to a per-session **bubblewrap** sandbox (no copies, no ldd parsing, mount/pid/ipc/uts/net namespaces, `/media/usb` bound as the sandbox root). Fix implemented on `version-2`. To validate on run 16. | #260 |
| 2 | Multiple `socat` listeners per direct_mount domain, one pair constantly restarting (PIDs changed between observations) while the boot pair stayed stable: `start_channel` was not idempotent, so a double start of the service duplicated the listeners (the late ones fail to bind and loop). | Fix implemented on `version-2`: `start_channel` stops the existing instance (pidfile) and removes the stale socket before starting, and the children's output is redirected to a per-domain log. Run 16 forensics (service log « starting » count, `ps -o pid,ppid`, openrc logs) to identify the double-start trigger. | #260 |
| 3 | `df` stuck on the business domains and no `/media/usb` mount point (the FUSE mount is dead but present — consequence of 1). | Consequence of 1. At run 16: `fusermount -u /media/usb` on the business domains (or a cold boot) before re-testing. | — |
