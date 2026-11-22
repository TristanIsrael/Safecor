# Run 16

Purpose: validate the #260 fix re-implemented as a per-session bubblewrap sandbox (run 15: the boot-time chroot was empty — musl `ldd` format), the #262 fix (the domid write race in `reboot-domain.sh`), diagnose the debug tty regression (Phase D), and re-validate the five objectives of `test-channels-migration.md`.

Preparation:
- [x] Rebuild the `safecor-sys-usb` package from `version-2` (the bubblewrap switch + the idempotent `start_channel` + the hot-plug hook + the dedicated `svc-sys-usb-sftp` service account; new dependencies `bubblewrap`, `setpriv`)
- [x] On Dom0: `apk update && apk add safecor-core` (and the rebuilt package on the DomUs at reprovisioning)
- [x] Full cold boot in debug mode with a USB disk connected before boot
- [ ] On the business domains with `direct_mount`: `fusermount -u /media/usb` (the run-15 FUSE mount is dead) — or rely on the cold boot

Smoke test (sys-usb, before any other check — proves bwrap works under the DomU kernel, that the setpriv switch to the service account works, and that sftp-server execs in the sandbox):
- [x] `bwrap --version` works
  - OK
```
bwrap --version
bubblewrap 0.12.0
```
- [x] `id svc-sys-usb-sftp` returns an account (created by the package post-install)
  - `uid=1001(svc-sys-usb-sftp) gid=2000(safecor) groups=2000(safecor),2000(safecor)`
- [ ] The SFTP handshake succeeds in the sandbox (an `SFTP_VERSION` answer is printed):
  - `printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 bwrap --bind /media/usb / --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --ro-bind /usr/bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 | xxd | head`
  - Expected: a line starting with `0000000c 00000002 00000003`
  - KO
```
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5
 bwrap --bind /media/usb / --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-
server --ro-bind /usr/bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64
.so.1 /lib/ld-musl-x86_64.so.1 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP
_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-u
ts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u
 svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-
server -u 077 | xxd | head
bwrap: Can't find source path /usr/bin/setpriv: No such file or directory
```
  - `setpriv` is in `/bin`  
  - If it fails: check `/var/log/safecor/vchan-*.log`, and whether sftp-server needs more files in the sandbox (e.g. `/etc/passwd`) — add the missing `--ro-bind` in that case (dedicated follow-up commit)
    - After replacing `/usr/bin/setpriv` with `/bin/setpriv` I got:
```
Error loading shared library libcap-ng.so.0: No such file or directory (needed by /usr/bin/setpriv)
Error loading shared library libeconf.so.0: No such file or directory (needed by /usr/bin/setpriv)
Error relocating /usr/bin/setpriv: capng_have_capability: symbol not found
Error relocating /usr/bin/setpriv: capng_capability_to_name: symbol not found
Error relocating /usr/bin/setpriv: econf_getStringValue: symbol not found
Error relocating /usr/bin/setpriv: capng_update: symbol not found
Error relocating /usr/bin/setpriv: capng_name_to_capability: symbol not found
Error relocating /usr/bin/setpriv: econf_readConfig: symbol not found
Error relocating /usr/bin/setpriv: capng_apply: symbol not found
Error relocating /usr/bin/setpriv: econf_errString: symbol not found
```
  - After adding `--ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0` I got error `setpriv: failed to execute /usr/lib/ssh/sftp-server: Permission denied`.
  - The directory `/media/usb/usr` was `0700`, we need to create the folders with the args `--dir /usr/lib --dir /usr/lib/ssh --dir /lib --dir /usr/bin`
  - After adding permissions (`bwrap --bind /media/usb / --dir /usr --dir /usr/lib --dir /usr/lib/ssh --dir /lib --dir /usr/bin --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --ro-bind /bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077`) I got the error `No user found for uid 1001`
  - I created a file /etc/sftp-sandbox-passwd with `echo 'svc-sys-usb-sftp:x:1001:2000::/:/sbin/nologin' > /etc/sftp-sandbox-passwd && chmod 644 /etc/sftp-sandbox-passwd`
  - I added a bind of this file to `/etc/passwd`: `bwrap --bind /media/usb / --dir /etc --dir /usr --dir /usr/lib --dir /usr/lib/ssh --dir /lib --dir /usr/bin --ro-bind /etc/sftp-sandbox-passwd /etc/passwd --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --ro-bind /bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077` and finally I got no error.
  - Then I tested with `printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5  bwrap --bind /media/usb / --dir /etc --dir /usr --dir /usr/lib --dir /usr/lib/ssh --dir /lib --dir /usr/bin --ro-bind /etc/sftp-sandbox-passwd /etc/passwd --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --ro-bind /bin/setpriv /usr/bin/setpriv --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0 --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir / -- /usr/bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077  | xxd | head` and got no output. The exit code was 0.

>>> Ended the tests here

### The fixed production smoke (new #260 commit — tmpfs sandbox root)

The production script now resolves everything dynamically at start: `shutil.which("setpriv")` (the binary is in `/bin` on this target), `ldd` for setpriv's shared libraries (libeconf + libcap-ng on Alpine 3.24), and a minimal one-account `/etc/passwd` written to `/usr/lib/safecor/etc/sftp-sandbox-passwd`. The sandbox root is a private tmpfs: `/media/usb` is bound at the same path and made the working directory (the SFTP root), so no junk directory ever reaches the system disk or the client.

Prerequisite: rebuild the `safecor-sys-usb` package from `version-2` (the new commit) and reinstall it on sys-usb.

Setup (once, as root — what the production script does at start; the file lives in `/usr/lib/safecor/etc`):
```
mkdir -p /usr/lib/safecor/etc
echo "svc-sys-usb-sftp:x:$(id -u svc-sys-usb-sftp):$(id -g svc-sys-usb-sftp)::/:/sbin/nologin" > /usr/lib/safecor/etc/sftp-sandbox-passwd
chmod 644 /usr/lib/safecor/etc/sftp-sandbox-passwd
```

- [x] The SFTP handshake succeeds in the sandbox (an `SFTP_VERSION` answer is printed) — the exact production command (Alpine 3.24 values):
```
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 bwrap --tmpfs / --dir /media/usb --bind /media/usb /media/usb --dir /etc --ro-bind /usr/lib/safecor/etc/sftp-sandbox-passwd /etc/passwd --dir /bin --ro-bind /bin/setpriv /bin/setpriv --dir /lib --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --dir /usr --dir /usr/lib --ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0 --dir /usr/lib/ssh --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir /media/usb -- /bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 | xxd | head
```
  - Expected: a line starting with `0000000c 00000002 00000003`
    - KO. Nothing is written
  - Then: `ls -la /media/usb` musgit statust list only the disk subdirectories (no `/usr`, `/lib`, `/etc`, `/bin` — the sandbox root is a tmpfs, gone with the session)
    - KO. The fodler is empty.
  - If it is still silent (exit code 0, no answer), run the probes A/B/C below before anything else:
    - **A — host, no sandbox** (does sftp-server answer at all for this account on this target?):
```
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 /bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 | xxd | head
```
      - KO.
      - **A' — host, root, no setpriv, stderr captured** (isolates the setuid switch; also checks the sftp-server binary itself):
```
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 /usr/lib/ssh/sftp-server -u 077 2>/tmp/sftp-a.err | xxd | head; echo "exit=$?"; cat /tmp/sftp-a.err; rm -f /tmp/sftp-a.err
apk info -v openssh-sftp-server
```
        - If A' is silent too: the sftp-server binary does not answer a piped SFTP_INIT on this target (version issue — compare with the run-15 version)
        - If A' answers but A does not: the setuid switch to `svc-sys-usb-sftp` is the cause
    - **B — sandbox, liveness + stdin through a held-open fifo** (separates "process died" from "process alive but the pipe never reached it"):
```
mkfifo /tmp/sftp.in
( sleep 300 > /tmp/sftp.in ) & WRITER=$!
timeout 30 bwrap --tmpfs / --dir /media/usb --bind /media/usb /media/usb --dir /etc --ro-bind /usr/lib/safecor/etc/sftp-sandbox-passwd /etc/passwd --dir /bin --ro-bind /bin/setpriv /bin/setpriv --dir /lib --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --dir /usr --dir /usr/lib --ro-bind /usr/lib/libeconf.so.0 /usr/lib/libeconf.so.0 --ro-bind /usr/lib/libcap-ng.so.0 /usr/lib/libcap-ng.so.0 --dir /usr/lib/ssh --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --cap-drop ALL --cap-add CAP_SETUID --cap-add CAP_SETGID --cap-add CAP_SETPCAP --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir /media/usb -- /bin/setpriv --reuid $(id -u svc-sys-usb-sftp) --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 < /tmp/sftp.in > /tmp/sftp.out 2>/tmp/sftp.err &
sleep 2
ps ax | grep '[s]ftp-server'            # is the process alive? note the pid
ls -l /proc/<pid>/fd                    # is fd 0 the fifo?
cat /proc/<pid>/wchan                   # where is it blocked?
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' > /tmp/sftp.in   # inject the INIT
sleep 2
xxd /tmp/sftp.out; cat /tmp/sftp.err
kill $WRITER 2>/dev/null; rm -f /tmp/sftp.in /tmp/sftp.out /tmp/sftp.err
```
      (the `sleep 300 > fifo` holds the write end open so the reader side never sees EOF; replace `<pid>` with the pid from `ps`)
    - **C — sandbox, no setpriv** (sftp-server runs as root in the sandbox; isolates the setuid switch — it needs a root line in its passwd):
```
echo "root:x:0:0::/:/sbin/nologin" > /tmp/probe-c-passwd && chmod 644 /tmp/probe-c-passwd
printf '\x00\x00\x00\x0c\x00\x00\x00\x01\x00\x00\x00\x03' | timeout 5 bwrap --tmpfs / --dir /media/usb --bind /media/usb /media/usb --dir /etc --ro-bind /tmp/probe-c-passwd /etc/passwd --dir /lib --ro-bind /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1 --dir /usr --dir /usr/lib/ssh --ro-bind /usr/lib/ssh/sftp-server /usr/lib/ssh/sftp-server --dev /dev --unshare-pid --unshare-ipc --unshare-uts --unshare-net --die-with-parent --chdir /media/usb -- /usr/lib/ssh/sftp-server -u 077 | xxd | head
rm -f /tmp/probe-c-passwd
```

### Topology regression — `my_config` returns no `direct_mount` domains (diagnosis)

The service log says `no domains with direct_mount found in topology` although `topology.json` contains the `direct_mount` entries. The `version-2` code path was verified end to end (JSON → struct → `Topology` → `my_config` response), and the `direct_mount` support only exists on `version-2` (`main` has safecor-core 1.4.2 without it; the stale-topology fix `628ae9c` is also version-2 only). Three candidates:

1. the safecor library running on the Dom0 is a build **older than `628ae9c`** (the `my_config` handler then answers with an empty `domains` list — the "stale topology reference" bug);
2. the running Dom0 controller loaded the topology **before** the `direct_mount` entries were added to `topology.json` (the topology is cached in memory after first load and never reloaded);
3. the file the Dom0 reads (`/etc/safecor/topology.json`) is not the file inspected above.

Diagnostics (on the **Dom0**):
```
apk info -v safecor-core
grep -c direct_mount /usr/lib/safecor/_system.py /usr/lib/safecor/_response_factory.py
grep direct_mount /etc/safecor/topology.json | head -5
python3 -c "import sys; sys.path.insert(0, '/usr/lib/safecor'); from safecor import System; t = System.get_topology(); [print(d.name, repr(d.direct_mount)) for d in t.domains]"
```

- `grep -c` = 0 → the installed library predates the `direct_mount` support → rebuild the repository's `safecor-core` from the `version-2` tip (bump `pkgrel` so it is newer than the repository's) and `apk upgrade` on the Dom0.
- `grep direct_mount /etc/safecor/topology.json` empty → the Dom0's topology file has no `direct_mount` entries (wrong file / stale copy).
- the `python3` one-liner prints `{'mode': 'ro'}` for the antivirus domains but the service sees nothing → the running Dom0 controller holds a stale in-memory topology (loaded before the edit) → restart the Dom0 safecor service (or reboot).
- the one-liner prints `False` → the library reads a file without the entries → compare the file the library opens with the one inspected.

Forensics — the run-15 socat duplication (identify the double-start trigger):
- [x] `tail -50 /var/log/safecor/vchan-sftp.log` — how many « starting » lines (script invocations)?
  - The file `var/log/safecor/vchan-sftp.log` contains the error `safecor-vchan-sftp: no domains with direct_mount found in topology` (this is a regression) but the file topology.json contains
```
"domains": [
    {
        "name": "saphir-gui",
        "app-package": "saphir-gui",
        "memory": 1200,
        "has_gui": 1,
        "vcpu_group": "gui",
        "temp_disk_size": 1024
    },
    {
        "name": "saphir-av-clamav",
        "app-package": "saphir-av-clamav",
        "memory": 3000,
        "vcpu_group": "antivirus",
        "temp_disk_size": 4096,
        "swap_size": 1024,
        "direct_mount": { "mode": "ro" }
    },
    {
        "name": "saphir-av-eset",
        "app-package": "saphir-av-eset",
        "memory": 2100,
        "vcpu_group": "antivirus",
        "temp_disk_size": 4096,
        "swap_size": 1024,
        "direct_mount": { "mode": "ro" }
    }
]
```
- [ ] `ps -o pid,ppid,lstart,args -ax | grep -E "socat|vchan-socket-proxy|bwrap" | grep -v grep` — who spawned the late socat (ppid)?
- [ ] `grep -i "safecor-vchan-sftp" /var/log/messages` — openrc start/stop activity

Verification — #260, the sshfs direct mount (bubblewrap):
- [ ] On sys-usb, one `socat UNIX-LISTEN:/var/run/safecor/vchan-<name>.sock,fork EXEC:"bwrap ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/vchan-<name>.sock` per direct_mount domain — no duplicated listeners, no restart loop
- [ ] On sys-usb, when a client connects, an sftp session runs in the sandbox: `ps ax | grep bwrap` shows `bwrap --tmpfs / --dir /media/usb --[ro-]bind /media/usb /media/usb ... /bin/setpriv --reuid <uid> --regid 2000 --clear-groups --no-new-privs /usr/lib/ssh/sftp-server -u 077 [-R]`, no zombie accumulation
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
