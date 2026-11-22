# Run 17

Purpose: validate the **event-driven refactoring of the direct USB mount** (issue #253, [`docs/plans/direct-mount-event-driven.md`](../direct-mount-event-driven.md)) on hardware, and resolve the two open regressions carried from [run 16](run-16.md): the **stale-topology** bug (fixed by a Dom0 reboot) and the **empty `/media/usb`** mdev regression.

> **What changed since run 16** (the design under test):
> - The SFTP channels are **no longer a separate `safecor-vchan-sftp` service** (deleted). They are started by the **`SysUsbController`** (the `safecor-sys-usb-controller` service) through the **`safecor-dm-channels.py`** root helper (via `doas`), and their readiness is published as the **`safecor_direct_mount`** component — the single synchronization point of the feature (NFR-3).
> - The runtime files (socket, pidfiles, per-domain log, sandbox passwd) live in **`/var/run/safecor/direct-mount/`** (created by the controller initd, owned by `svc-sys-usb-controller`).
> - The **`DirectMountManager`** (DomU side) is now **event-driven**: it keeps a persistent MQTT client, mounts `/media/usb` when `safecor_direct_mount` is `READY`, unmounts on `OFF`, and a watchdog remounts when sshfs dies. The mount is **proactive at the end of the domain startup and kept permanent**, whether or not a USB disk is connected.
> - `/media/usb` is mounted on **every** `direct_mount` business DomU at boot (even with no disk).

Preparation:
- [ ] Rebuild **`safecor-lib`** and **`safecor-sys-usb`** from the `version-2` tip (no version bump — refactoring branch). `safecor-lib` carries the new `SysUsbController` + `DirectMountManager` + `MountMode`; `safecor-sys-usb` carries the `safecor-dm-channels.py` helper, the rewritten initd, the doas config and the removal of the `safecor-vchan-sftp` files. (See [../../development/packaging.md](../../development/packaging.md).)
- [ ] Install `safecor-lib` on the **Dom0**, **sys-usb** and the business DomUs; install `safecor-sys-usb` on **sys-usb** (the post-install stops/`rc-update del`s the old `safecor-vchan-sftp` service — the upgrade path).
- [ ] **Reboot the Dom0** — this is the fix for the run-16 stale-topology regression (the running controller re-reads `topology.json`, which now has the `direct_mount` entries). No rebuild is needed for that bug.
- [ ] Full cold boot in debug mode with **a USB disk connected before boot**.
- [ ] Confirm the old service is gone on sys-usb: `rc-status | grep vchan-sftp` → nothing; `ls /etc/init.d/safecor-vchan-sftp` → missing.

## 1. Smoke test (sys-usb — the controller starts the channels)

These prove the new start path works before checking the business domains.

- [ ] The controller service is up: `rc-status safecor-sys-usb-controller` → `started`; the process runs as `svc-sys-usb-controller`: `ps ax | grep safecor-sys-usb-controller | grep -v grep`.
- [ ] The runtime dir is created and owned by the controller: `ls -ld /var/run/safecor/direct-mount` → `drwxrwx--- ... svc-sys-usb-controller safecor`.
- [ ] The doas grant is present: `cat /etc/doas.d/svc-sys-usb-controller.conf` shows `permit nopass svc-sys-usb-controller as root cmd /usr/lib/safecor/bin/safecor-dm-channels.py`.
- [ ] The helper is installed: `ls -l /usr/lib/safecor/bin/safecor-dm-channels.py`.
- [ ] **Per `direct_mount` domain** (`saphir-av-clamav`, `saphir-av-eset` in the current topology), on sys-usb there is one socat and one vchan server, with the **new** socket path, no duplicates, no restart loop:
  ```
  ps -o pid,user,args -ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep
  ```
  - Expected, per domain `<name>`: one `socat UNIX-LISTEN:/var/run/safecor/direct-mount/vchan-<name>.sock,fork EXEC:"bwrap ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/direct-mount/vchan-<name>.sock`.
- [ ] The per-domain log exists and shows a clean start (no error): `cat /var/run/safecor/direct-mount/vchan-<name>.log`.

## 2. The `safecor_direct_mount` component (the synchronization point)

- [ ] On a business domain, the component is reported **`READY`** on the bus (a direct one-shot check — the state must be `ready` once the channels are up):
  ```
  python3 - <<'PY'
  import sys, threading
  sys.path.insert(0, "/usr/lib/safecor")
  from safecor import Api, MqttFactory, Topics, Constants
  done, result = threading.Event(), {}
  def on_message(topic, payload):
      if topic == f"{Topics.DISCOVER_COMPONENTS}/response":
          for c in payload.get("components", []):
              if c.get("id") == Constants.SAFECOR_DIRECT_MOUNT:
                  result["state"] = c.get("state"); done.set()
  def on_ready():
      Api().discover_components()
  Api().add_ready_callback(on_ready); Api().add_message_callback(on_message)
  Api().start(MqttFactory.create_mqtt_client_domu("component-check"))
  done.wait(timeout=15)
  print("safecor_direct_mount state:", result.get("state", "NOT FOUND (timeout)"))
  PY
  ```
  - Expected: `safecor_direct_mount state: ready`. (If `starting`: the one-shot `my_config` query timed out — check the sys-usb controller log; the component stays `starting` by design, **no retry**.)
- [ ] **Behavioral proof (primary)**: the component reaching `READY` is exactly what makes the business domains mount (section 3). If `/media/usb` is mounted there, the component was `READY`.

## 3. The event-driven mount on the business DomUs

On each `direct_mount` business domain (`saphir-av-clamav`, `saphir-av-eset`):

- [ ] The `direct-mount` manager process is running: `ps ax | grep direct-mount | grep -v grep`.
- [ ] `/media/usb` is mounted **automatically at the end of boot** (proactive, before any disk is needed): `mount | grep /media/usb` and `df /media/usb` return.
- [ ] The mount is via sshfs over vchan with the expected options: `ps ax | grep sshfs | grep -v grep` shows `sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,...,reconnect[,ro] none:/ /media/usb`.
  - `ro` domains end with `,ro`; `rw` domains do not.
- [ ] The manager log (mirrored on stderr; from the openrc console or `rc-service direct-mount status`) shows: `direct_mount enabled (mode=ro)` then `/media/usb mounted (mode=ro)`.
- [ ] With **no USB disk connected**, the mount still succeeds (empty tree): `ls /media/usb` → empty, no error. (This is the "permanent even when empty" requirement.)

## 4. File I/O through the mount (requires the `/media/usb` regression in section 5 to be fixed first)

- [ ] `ro` domain: a file from the USB disk connected before boot is readable at the same path as on sys-usb: `cat /media/usb/<disk>/<file>`.
- [ ] `ro` domain: a write through the mount is **refused**: `touch /media/usb/<disk>/x` → `Read-only file system`.
- [ ] `rw` domain (if any `rw` `direct_mount` domain exists): a file written through the mount appears on the USB disk, and a file written on the disk appears through the mount.
- [ ] **Watchdog remount**: on a business domain, kill sshfs (`pkill -f 'sshfs .*none:/.*\/media/usb'` or `fusermount -u /media/usb`); the watchdog remounts within a few seconds (`mount | grep /media/usb` comes back) and the manager log shows `the sshfs process terminated, remounting`.

## 5. Regression — empty `/media/usb` on sys-usb (mdev)

Run 16 found `/media/usb` empty on sys-usb although a disk was connected before boot. This is a **separate** bug (the mdev mount hook did not mount the disks) and must be fixed for sections 3/4 to serve real files. Diagnose on **sys-usb**:

- [ ] Are the USB disks seen as block devices? `lsblk` (expect `/dev/sdX` with a partition) and `dmesg | grep -iE "usb|sd[a-z]|mount" | tail -30`.
- [ ] Is the mdev hook firing? `tail -50 /var/log/messages | grep -iE "mdev|usb-storage|/media/usb"` and check `/etc/udiscv/mdev.conf` / the `99-usbdisks.rules` + `mdev-usb-storage.sh` wiring.
- [ ] Are the disks supposed to be mounted at `/media/usb/<label>`? `ls -la /media/usb` and, if a disk is present but unmounted, try a manual mount to confirm the filesystem: `mount /dev/sdX1 /tmp/probe && ls /tmp/probe && umount /tmp/probe`.
- [ ] Record the root cause and the fix (dedicated commit if code changes are needed). Until fixed, sections 3 "empty when no disk" and the manager mount still validate the **channel + component + event flow**; only the real-file I/O in section 4 is blocked.

## 6. The OFF path (sys-usb restart ⇒ unmount, then remount)

- [ ] On a business domain, `/media/usb` is mounted (from section 3).
- [ ] Restart sys-usb: `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_domu('reboot')); Api().restart_domain('sys-usb')"` (or the equivalent API call).
- [ ] While sys-usb is down / restarting, the business domain **unmounts** (the controller published `OFF`): `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`.
- [ ] After sys-usb comes back and its `safecor_direct_mount` is `READY` again, the business domain **remounts** automatically (no manual action): `mount | grep /media/usb` returns again.

## 7. Optional — confirm the SFTP "silence" is a test artifact (run 16)

Run 16 concluded the piped-INIT silence is an `openssh-sftp-server` 10.3p1 artifact (stdin EOF handled before the `SFTP_VERSION` flush), not a product bug. Confirm on hardware that a **real** SFTP client works end to end:
- [ ] With a disk connected and mounted (section 5 fixed), an `sftp` session through the vchan lists the files: on a business domain, `sftp -o "ProxyCommand=/usr/local/bin/vchan-sftp" none@localhost` → `ls` shows the USB tree. (Or simply rely on section 3/4 sshfs reads, which are the same SFTP channel.)
- [ ] (Optional probe E) Re-run the run-16 probe D and note that `exit=124` + empty output with a **held-open** stdin (probe B's fifo) yields the `SFTP_VERSION` answer — proving the process answers when the channel stays open.

## 8. Re-validate the five objectives + regressions (test-channels-migration.md)

- [ ] Messaging on all domains (local brokers, `msg` vchan bridge, client IDs `safecor-<domain>-bridge` on Dom0).
- [ ] Inputs on sys-usb (mouse/touch).
- [ ] GUI display (the GUI domain displays, the Saphir app starts, its messages are visible on the bus).
- [ ] The local brokers stay connected across the reboots tested above (including the sys-usb restart in section 6).
- [ ] No duplicate socat/vchan listeners and no restart loop after the sys-usb restart (idempotent `start_sftp_channel`).

## If everything is green

Close **#256** (and **#253** as validated, plus **#260**, **#262** if not already), update `docs/project-status.md`, check the objectives in `test-channels-migration.md`, and move to the second pass (Phase F: #259, #261). If the empty-`/media/usb` mdev bug needs a code fix, open a dedicated issue and commit before closing the mount objectives.
