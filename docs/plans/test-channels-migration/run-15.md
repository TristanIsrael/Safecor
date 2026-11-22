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
- [x] On sys-usb, the sftp chroot is built at boot: `ls -l /media/usb/usr/lib/ssh/` contains `sftp-server`, the shared libraries and `/lib64/ld-linux-x86-64.so.2`
  - `/media/usb/usr/lib/ssh/` only contains `sftp-server`
- [x] On sys-usb, for each direct_mount domain: one `socat UNIX-LISTEN:/var/run/safecor/vchan-<name>.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/vchan-<name>.sock` (the socat started before the proxy)
  - There are multiple `socat` for each client and 2 of them are constantly restarting: 
```
ps ax | grep "socat UNIX"
 2350 root      0:06 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-clamav.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
 2357 root      0:06 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-eset.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
15508 root      0:00 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-clamav.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
15511 root      0:00 grep socat UNIX
15512 root      0:00 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-eset.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
```
- [x] The `ro` domains get `sftp-server -u 077 -R`, the `rw` domains `-u 077` only
  - Lots of `sftp-server` processes are zombies and some of them have the correct options.
```
ps ax | grep sftp
 2350 root      0:13 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-clamav.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
 2352 root      0:01 /usr/bin/vchan-socket-proxy -m server 3 /local/domain/system/vchan/saphir-av-clamav/sftp /var/run/safecor/vchan-saphir-av-clamav.sock
 2357 root      0:13 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-eset.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
 2359 root      0:01 /usr/bin/vchan-socket-proxy -m server 4 /local/domain/system/vchan/saphir-av-eset/sftp /var/run/safecor/vchan-saphir-av-eset.sock
 3783 root      0:00 [sftp-server]
 3785 root      0:00 [sftp-server]
 3795 root      0:00 [sftp-server]
 3799 root      0:00 [sftp-server]
 3809 root      0:00 [sftp-server]
 3817 root      0:00 [sftp-server]
 3821 root      0:00 [sftp-server]
 3827 root      0:00 [sftp-server]
 3829 root      0:00 [sftp-server]
 3832 root      0:00 [sftp-server]
 3833 root      0:00 [sftp-server]
 3836 root      0:00 [sftp-server]
 3837 root      0:00 [sftp-server]
 3840 root      0:00 [sftp-server]
 3841 root      0:00 [sftp-server]
 3844 root      0:00 [sftp-server]
 3845 root      0:00 [sftp-server]
 3848 root      0:00 [sftp-server]
 3849 root      0:00 [sftp-server]
 3852 root      0:00 [sftp-server]
 3853 root      0:00 [sftp-server]
 3857 root      0:00 [sftp-server]
 3860 root      0:00 [sftp-server]
 3864 root      0:00 [sftp-server]
 3865 root      0:00 [sftp-server]
 3868 root      0:00 [sftp-server]
 3872 root      0:00 [sftp-server]
 3873 root      0:00 [sftp-server]
 3876 root      0:00 [sftp-server]
 3877 root      0:00 [sftp-server]
 3880 root      0:00 [sftp-server]
 3881 root      0:00 [sftp-server]
 3885 root      0:00 [sftp-server]
 3887 root      0:00 [sftp-server]
 3889 root      0:00 [sftp-server]
 3891 root      0:00 [sftp-server]
 3893 root      0:00 [sftp-server]
 3899 root      0:00 [sftp-server]
 3901 root      0:00 [sftp-server]
 3904 root      0:00 [sftp-server]
 3905 root      0:00 [sftp-server]
 3907 root      0:00 [sftp-server]
 3909 root      0:00 [sftp-server]
 3911 root      0:00 [sftp-server]
 3916 root      0:00 [sftp-server]
 3917 root      0:00 [sftp-server]
 3920 root      0:00 [sftp-server]
 3921 root      0:00 [sftp-server]
 3924 root      0:00 [sftp-server]
 3925 root      0:00 [sftp-server]
 3929 root      0:00 [sftp-server]
 3933 root      0:00 [sftp-server]
 3937 root      0:00 [sftp-server]
 3940 root      0:00 [sftp-server]
 3941 root      0:00 [sftp-server]
 3945 root      0:00 [sftp-server]
 3948 root      0:00 [sftp-server]
 3949 root      0:00 [sftp-server]
 3951 root      0:00 [sftp-server]
 3953 root      0:00 [sftp-server]
 3956 root      0:00 [sftp-server]
 3960 root      0:00 [sftp-server]
 3964 root      0:00 [sftp-server]
 3965 root      0:00 [sftp-server]
 3967 root      0:00 [sftp-server]
 3971 root      0:00 [sftp-server]
 3976 root      0:00 [sftp-server]
 3977 root      0:00 [sftp-server]
 3993 root      0:00 [sftp-server]
 3996 root      0:00 [sftp-server]
 4005 root      0:00 grep sftp
 4006 root      0:00 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-clamav.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
 4008 root      0:00 /usr/bin/socat UNIX-LISTEN:/var/run/safecor/vchan-saphir-av-eset.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server -u 077 -R"
```
- [x] On a business domain with `direct_mount`, `/media/usb` is mounted automatically at boot (`mount | grep /media/usb`)
  - KO. The command `df` is stucked and there is no `/media/usb`.
- [x] The sshfs options include `reconnect` (`cat /proc/$(pidof sshfs)/cmdline`)
  - OK
```
ps ax | grep sshfs
 2773 root      0:00 sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,noexec,nosuid,nodev,default_permissions,max_read=131072,reconnect,ro none:/ /media/usb
```
- [x] A file from the USB disk connected before boot is readable through the mount: `cat /media/usb/<disk>/<file>`
  - KO
- [ ] `rw` domain: a file written through the mount is visible on the USB disk (and vice versa)
  - Not tested
- [x] `ro` domain: a write through the mount is refused
  - Not tested because of previous errors
- [x] USB hot-plug: connect a second USB disk after boot, it appears in the `/media/usb` mount of the business domains without reboot
  - Not tested because of previous errors

>>> Test run ended here

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
