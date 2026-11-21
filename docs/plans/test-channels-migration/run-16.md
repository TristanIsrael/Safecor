# Run 16

Purpose: validate the #260 fix re-implemented as a per-session bubblewrap sandbox (run 15: the boot-time chroot was empty — musl `ldd` format), the #262 fix (the domid write race in `reboot-domain.sh`), diagnose the debug tty regression (Phase D), and re-validate the five objectives of `test-channels-migration.md`.

Preparation:
- [ ] Rebuild the `safecor-sys-usb` package from `version-2` (the bubblewrap switch + the idempotent `start_channel` + the hot-plug hook + the dedicated `svc-sys-usb-sftp` service account; new dependencies `bubblewrap`, `setpriv`)
- [ ] On Dom0: `apk update && apk add safecor-core` (and the rebuilt package on the DomUs at reprovisioning)
- [ ] Full cold boot in debug mode with a USB disk connected before boot
- [ ] On the business domains with `direct_mount`: `fusermount -u /media/usb` (the run-15 FUSE mount is dead) — or rely on the cold boot

Smoke test (sys-usb, before any other check — proves bwrap works under the DomU kernel, that the setpriv switch to the service account works, and that sftp-server execs in the sandbox):
- [ ] `bwrap --version` works
- [ ] `id svc-sys-usb-sftp` returns an account (created by the package post-install)
- [ ] The SFTP handshake succeeds in the sandbox (an `SFTP_VERSION` answer is printed):
  - `printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 bwrap --bind /media/usb / --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --ro-bind /usr/bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 | xxd | head`
  - Expected: a line starting with `0000000c 00000002 00000003`
  - If it fails: check `/var/log/safecor/vchan-*.log`, and whether sftp-server needs more files in the sandbox (e.g. `/etc/passwd`) — add the missing `--ro-bind` in that case (dedicated follow-up commit)

Forensics — the run-15 socat duplication (identify the double-start trigger):
- [ ] `tail -50 /var/log/safecor/vchan-sftp.log` — how many « starting » lines (script invocations)?
- [ ] `ps -o pid,ppid,lstart,args -ax | grep -E "socat|vchan-socket-proxy|bwrap" | grep -v grep` — who spawned the late socat (ppid)?
- [ ] `grep -i "safecor-vchan-sftp" /var/log/messages` — openrc start/stop activity

Verification — #260, the sshfs direct mount (bubblewrap):
- [ ] On sys-usb, one `socat UNIX-LISTEN:/var/run/safecor/vchan-<name>.sock,fork EXEC:"bwrap ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/vchan-<name>.sock` per direct_mount domain — no duplicated listeners, no restart loop
- [ ] On sys-usb, when a client connects, an sftp session runs in the sandbox: `ps ax | grep bwrap` shows `bwrap --bind /media/usb / ... /usr/bin/setpriv --reuid <uid> --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 [-R]`, no zombie accumulation
- [ ] The sftp-server process runs as `svc-sys-usb-sftp` with no capabilities: `ps ax | grep sftp-server` shows the user, and `CapEff: 0000000000000000` in `/proc/<sftp-pid>/status`
- [ ] A USB disk mount point is owned by the account: `stat -c '%U:%G %a' /media/usb/<disk>` → `svc-sys-usb-sftp:safecor 770`
- [ ] The `ro` domains get `sftp-server -u 077 -R`, the `rw` domains `-u 077` only
- [ ] On a business domain with `direct_mount`, `/media/usb` is mounted automatically at boot (`mount | grep /media/usb`, `df` returns)
- [ ] The sshfs options include `reconnect` (`ps ax | grep sshfs`)
- [ ] A file from the USB disk connected before boot is readable: `cat /media/usb/<disk>/<file>` (the disk must be at the same path as on sys-usb)
- [ ] `rw` domain: a file written through the mount is visible on the USB disk (and vice versa)
- [ ] `ro` domain: a write through the mount is refused
- [ ] USB hot-plug: connect a second USB disk after boot, it appears in the `/media/usb` mount of the business domains without reboot (the mdev hook kills the sessions, the clients' sshfs reconnects)
- [ ] USB hot-remove: unplug the second disk, it disappears from the `/media/usb` mount of the business domains

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
