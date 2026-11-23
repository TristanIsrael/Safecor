# Run 17

Purpose: validate the **event-driven refactoring of the direct USB mount** (issue #253, [`docs/plans/direct-mount-event-driven.md`](../direct-mount-event-driven.md)) on hardware, and resolve the two open regressions carried from [run 16](run-16.md): the **stale-topology** bug (fixed by a Dom0 reboot) and the **empty `/media/usb`** mdev regression.

> **What changed since run 16** (the design under test):
> - The SFTP channels are **no longer a separate `safecor-vchan-sftp` service** (deleted). They are started by the **`SysUsbController`** (the `safecor-sys-usb-controller` service) through the **`safecor-dm-channels.py`** root helper (via `doas`), and their readiness is published as the **`safecor_direct_mount`** component — the single synchronization point of the feature (NFR-3).
> - The runtime files (socket, pidfiles, per-domain log, sandbox passwd) live in **`/var/run/safecor/direct-mount/`** (created by the controller initd, owned by `svc-sys-usb-controller`).
> - The **`DirectMountManager`** (DomU side) is now **event-driven**: it keeps a persistent MQTT client, mounts `/media/usb` when `safecor_direct_mount` is `READY`, unmounts on `OFF`, and a watchdog remounts when sshfs dies. The mount is **proactive at the end of the domain startup and kept permanent**, whether or not a USB disk is connected.
> - `/media/usb` is mounted on **every** `direct_mount` business DomU at boot (even with no disk).

Preparation:
- [x] Rebuild **`safecor-lib`** and **`safecor-sys-usb`** from the `version-2` tip (no version bump — refactoring branch). `safecor-lib` carries the new `SysUsbController` + `DirectMountManager` + `MountMode`; `safecor-sys-usb` carries the `safecor-dm-channels.py` helper, the rewritten initd, the doas config and the removal of the `safecor-vchan-sftp` files. (See [../../development/packaging.md](../../development/packaging.md).)
- [x] Install `safecor-lib` on the **Dom0**, **sys-usb** and the business DomUs; install `safecor-sys-usb` on **sys-usb** (the post-install stops/`rc-update del`s the old `safecor-vchan-sftp` service — the upgrade path).
- [x] **Reboot the Dom0** — this is the fix for the run-16 stale-topology regression (the running controller re-reads `topology.json`, which now has the `direct_mount` entries). No rebuild is needed for that bug.
- [x] Full cold boot in debug mode with **a USB disk connected before boot**.
- [x] Confirm the old service is gone on sys-usb: `rc-status | grep vchan-sftp` → nothing; `ls /etc/init.d/safecor-vchan-sftp` → missing.
  - OK

## 1. Smoke test (sys-usb — the controller starts the channels)

These prove the new start path works before checking the business domains.

- [x] The controller service is up: `rc-status safecor-sys-usb-controller` → `started`; the process runs as `svc-sys-usb-controller`: `ps ax | grep safecor-sys-usb-controller | grep -v grep`.
- [x] The runtime dir is created and owned by the controller: `ls -ld /var/run/safecor/direct-mount` → `drwxrwx--- ... svc-sys-usb-controller safecor`.
  - OK
- [x] The doas grant is present: `cat /etc/doas.d/svc-sys-usb-controller.conf` shows `permit nopass svc-sys-usb-controller as root cmd /usr/lib/safecor/bin/safecor-dm-channels.py`.
- [x] The helper is installed: `ls -l /usr/lib/safecor/bin/safecor-dm-channels.py`.
- [x] **Per `direct_mount` domain** (`saphir-av-clamav`, `saphir-av-eset` in the current topology), on sys-usb there is one socat and one vchan server, with the **new** socket path, no duplicates, no restart loop:
  ```
  ps -o pid,user,args -ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep
  ```
  - Expected, per domain `<name>`: one `socat UNIX-LISTEN:/var/run/safecor/direct-mount/vchan-<name>.sock,fork EXEC:"bwrap ..."` and one `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/direct-mount/vchan-<name>.sock`.
  - `ps | grep -E 'socat UNIX-LISTEN|vchan-socket-proxy -m server' | grep -v grep` returns nothing
- [x] The per-domain log exists and shows a clean start (no error): `cat /var/run/safecor/direct-mount/vchan-<name>.log`.
  - The directory exists but is empty

## 2. The `safecor_direct_mount` component (the synchronization point)

- [x] On a business domain, the component is reported **`READY`** on the bus (a direct one-shot check — the state must be `ready` once the channels are up):
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
  - KO: `safecor_direct_mount state: NOT FOUND (timeout)` but in the message bus I have:
```
{
  "components": [
    {
      "id": "safecor_disk_controller",
      "domain_name": "sys-usb",
      "label": "System disk controller",
      "type": "core",
      "state": "ready"
    },
    {
      "id": "safecor_input_controller",
      "domain_name": "sys-usb",
      "label": "Input controller",
      "type": "core",
      "state": "ready"
    },
    {
      "id": "safecor_direct_mount",
      "domain_name": "sys-usb",
      "label": "Direct USB mount (SFTP channels)",
      "type": "core",
      "state": "ready"
    }
  ]
}
```
- [x] **Behavioral proof (primary)**: the component reaching `READY` is exactly what makes the business domains mount (section 3). If `/media/usb` is mounted there, the component was `READY`.
  - Unsure. In `saphir-av-clamav` I have `none:/ on /media/usb type fuse.sshfs (ro,nosuid,nodev,noexec,relatime,user_id=0,group_id=0,default_permissions)` in `mount`. But when I run `df` it gets stucked.
  - I am a little surprized that the package `safecor-domu-base` has not been impacted by the last changes. I suppose the moment the sshfs is mounted depends on the readiness of the `DirectMountManager` in `sys-usb`.

## 3. The event-driven mount on the business DomUs

On each `direct_mount` business domain (`saphir-av-clamav`, `saphir-av-eset`):

- [x] The `direct-mount` manager process is running: `ps ax | grep direct-mount | grep -v grep`.
  - OK
- [x] `/media/usb` is mounted **automatically at the end of boot** (proactive, before any disk is needed): `mount | grep /media/usb` and `df /media/usb` return.
  - It seems to be there but when I try to `ls /media` it gets stucked with no result.
- [x] The mount is via sshfs over vchan with the expected options: `ps ax | grep sshfs | grep -v grep` shows `sshfs -f -o ssh_command=/usr/local/bin/vchan-sftp,...,reconnect[,ro] none:/ /media/usb`.
  - `ro` domains end with `,ro`; `rw` domains do not.
  - OK
- [x] The manager log (mirrored on stderr; from the openrc console or `rc-service direct-mount status`) shows: `direct_mount enabled (mode=ro)` then `/media/usb mounted (mode=ro)`.
  - Here are the logs in `/var/log/messages`:
```
Nov 22 16:56:06 saphir-av-clamav daemon.info Safecor/MQTT-client[2684]: Starting MQTT client direct-mount-manager
Nov 22 16:56:06 saphir-av-clamav daemon.notice mosquitto[2453]: 1795366566: New client connected from /var/run/safecor/mqtt.sock:0 as direct-mount-manager (p4, c1, k30).
```
- [x] With **no USB disk connected**, the mount still succeeds (empty tree): `ls /media/usb` → empty, no error. (This is the "permanent even when empty" requirement.)
  - Not tried because I started with a disk connected

## 4. File I/O through the mount (requires the `/media/usb` regression in section 5 to be fixed first)

- [ ] `ro` domain: a file from the USB disk connected before boot is readable at the same path as on sys-usb: `cat /media/usb/<disk>/<file>`.
- [ ] `ro` domain: a write through the mount is **refused**: `touch /media/usb/<disk>/x` → `Read-only file system`.
- [ ] `rw` domain (if any `rw` `direct_mount` domain exists): a file written through the mount appears on the USB disk, and a file written on the disk appears through the mount.
- [ ] **Watchdog remount**: on a business domain, kill sshfs (`pkill -f 'sshfs .*none:/.*\/media/usb'` or `fusermount -u /media/usb`); the watchdog remounts within a few seconds (`mount | grep /media/usb` comes back) and the manager log shows `the sshfs process terminated, remounting`.

## 5. Regression — empty `/media/usb` on sys-usb (mdev)

Run 16 found `/media/usb` empty on sys-usb although a disk was connected before boot. This is a **separate** bug (the mdev mount hook did not mount the disks) and must be fixed for sections 3/4 to serve real files. Diagnose on **sys-usb**:

- [x] Are the USB disks seen as block devices? `lsblk` (expect `/dev/sdX` with a partition) and `dmesg | grep -iE "usb|sd[a-z]|mount" | tail -30`.
- [x] Is the mdev hook firing? `tail -50 /var/log/messages | grep -iE "mdev|usb-storage|/media/usb"` and check `/etc/udiscv/mdev.conf` / the `99-usbdisks.rules` + `mdev-usb-storage.sh` wiring.
- [x] Are the disks supposed to be mounted at `/media/usb/<label>`? `ls -la /media/usb` and, if a disk is present but unmounted, try a manual mount to confirm the filesystem: `mount /dev/sdX1 /tmp/probe && ls /tmp/probe && umount /tmp/probe`.
- [x] Record the root cause and the fix (dedicated commit if code changes are needed). Until fixed, sections 3 "empty when no disk" and the manager mount still validate the **channel + component + event flow**; only the real-file I/O in section 4 is blocked.

>> The external storage is correctly mounted. 

## 6. The OFF path (sys-usb restart ⇒ unmount, then remount)

- [ ] On a business domain, `/media/usb` is mounted (from section 3).
- [ ] Restart sys-usb: `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_domu('reboot')); Api().restart_domain('sys-usb')"` (or the equivalent API call).
- [ ] While sys-usb is down / restarting, the business domain **unmounts** (the controller published `OFF`): `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`.
- [ ] After sys-usb comes back and its `safecor_direct_mount` is `READY` again, the business domain **remounts** automatically (no manual action): `mount | grep /media/usb` returns again.

>> Not tested due to previous errors

## 7. Optional — confirm the SFTP "silence" is a test artifact (run 16)

Run 16 concluded the piped-INIT silence is an `openssh-sftp-server` 10.3p1 artifact (stdin EOF handled before the `SFTP_VERSION` flush), not a product bug. Confirm on hardware that a **real** SFTP client works end to end:
- [x] With a disk connected and mounted (section 5 fixed), an `sftp` session through the vchan lists the files: on a business domain, `sftp -o "ProxyCommand=/usr/local/bin/vchan-sftp" none@localhost` → `ls` shows the USB tree. (Or simply rely on section 3/4 sshfs reads, which are the same SFTP channel.)
  - Tried on `saphir-av-clamav` and the command does not return
- [ ] (Optional probe E) Re-run the run-16 probe D and note that `exit=124` + empty output with a **held-open** stdin (probe B's fifo) yields the `SFTP_VERSION` answer — proving the process answers when the channel stays open.

## 8. Re-validate the five objectives + regressions (test-channels-migration.md)

- [x] Messaging on all domains (local brokers, `msg` vchan bridge, client IDs `safecor-<domain>-bridge` on Dom0).
- [x] Inputs on sys-usb (mouse/touch).
- [x] GUI display (the GUI domain displays, the Saphir app starts, its messages are visible on the bus).
- [ ] The local brokers stay connected across the reboots tested above (including the sys-usb restart in section 6). -> Not tested yet
- [ ] No duplicate socat/vchan listeners and no restart loop after the sys-usb restart (idempotent `start_sftp_channel`). -> Not tested yet

## If everything is green

Close **#256** (and **#253** as validated, plus **#260**, **#262** if not already), update `docs/project-status.md`, check the objectives in `test-channels-migration.md`, and move to the second pass (Phase F: #259, #261). If the empty-`/media/usb` mdev bug needs a code fix, open a dedicated issue and commit before closing the mount objectives.

## Complimentary analysis

- `grep -iE "usb controller|SFTP|channels helper|direct_mount|domid" /var/log/messages` on `sys-usb`
```
Nov 22 16:55:54 sys-usb user.info Safecor/setup-vchan.sh: vchan input client started (domid=1, sock=/var/run/safecor/input.sock)
Nov 22 16:55:54 sys-usb user.info Safecor/setup-vchan.sh: vchan tty client started (domid=1, sock=/var/run/safecor/tty.sock)
```
- `xenstore-ls /local/domain/system/domids` on Dom0:
```
sys-usb = "1"
saphir-gui = "2"
saphir-av-clamav = "3"
saphir-av-eset = "4"
```
- `id svc-sys-usb-sftp` on `sys-usb`:
```
uid=1001(svc-sys-usb-sftp) gid=2000(safecor) groups=2000(safecor),2000(safecor)
```
- `which sepriv` on `sys-usb`:
`/bin/setpriv`

- `grep -n "USB controller" /var/log/safecor/messages.log | head -60`
```
3:[2026-11-22 17:55:55] system/events/debug {"component": "sys-usb", "module": "USB controller", "datetime": "2026-11-22 16:55:55.062", "description": "Starting Safecor disk controller"}
13:[2026-11-22 17:55:55] system/events/warning {"component": "sys-usb", "module": "USB controller", "datetime": "2026-11-22 16:55:55.664", "description": "No domid found for domain saphir-av-clamav, its SFTP channel is skipped"}
16:[2026-11-22 17:55:55] system/events/warning {"component": "sys-usb", "module": "USB controller", "datetime": "2026-11-22 16:55:55.670", "description": "No domid found for domain saphir-av-eset, its SFTP channel is skipped"}
87:[2026-11-22 17:56:30] system/events/debug {"component": "sys-usb", "module": "USB controller", "datetime": "2026-11-22 16:56:30.583", "description": "Disks list requested"}
```

- `grep -n "safecor_direct_mount" /var/log/safecor/messages.log | head -30`
```
5:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "starting"}]}
9:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "starting"}]}
17:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
27:[2026-11-22 17:56:06] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
28:[2026-11-22 17:56:06] system/events/info {"component": "saphir-av-clamav", "module": "Api", "datetime": "2026-11-22 16:56:06.600", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
47:[2026-11-22 17:56:11] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
48:[2026-11-22 17:56:11] system/events/info {"component": "saphir-av-eset", "module": "Api", "datetime": "2026-11-22 16:56:11.676", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
62:[2026-11-22 17:56:26] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
63:[2026-11-22 17:56:26] system/events/info {"component": "saphir-gui", "module": "Api", "datetime": "2026-11-22 16:56:27.202", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
73:[2026-11-22 17:56:30] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
85:[2026-11-22 17:56:30] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
152:[2026-11-22 17:58:14] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
327:[2026-11-22 18:05:08] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
```

- `grep -nE "my_config|direct_mount" /var/log/safecor/messages.log | head -40`
```
5:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "starting"}]}
6:[2026-11-22 17:55:55] system/topology/my_config/request {}
8:[2026-11-22 17:55:55] system/topology/my_config/request {"domain_name": "sys-usb"}
9:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "starting"}]}
11:[2026-11-22 17:55:55] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "sys-usb", "domain_type": 1, "direct_mount": false}, {"name": "saphir-gui", "domain_type": 2, "direct_mount": false}, {"name": "saphir-av-clamav", "domain_type": 2, "direct_mount": {"mode": "ro"}}, {"name": "saphir-av-eset", "domain_type": 2, "direct_mount": {"mode": "ro"}}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
12:[2026-11-22 17:55:55] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "sys-usb", "domain_type": 1, "direct_mount": false}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
14:[2026-11-22 17:55:55] system/events/info {"component": "sys-usb", "module": "Api", "datetime": "2026-11-22 16:55:55.664", "description": "direct_mount is not enabled for this domain, exiting"}
17:[2026-11-22 17:55:55] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
26:[2026-11-22 17:56:06] system/topology/my_config/request {"domain_name": "saphir-av-clamav"}
27:[2026-11-22 17:56:06] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
28:[2026-11-22 17:56:06] system/events/info {"component": "saphir-av-clamav", "module": "Api", "datetime": "2026-11-22 16:56:06.600", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
30:[2026-11-22 17:56:06] system/topology/my_config/request {"domain_name": "saphir-av-clamav"}
32:[2026-11-22 17:56:06] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-av-clamav", "domain_type": 2, "direct_mount": {"mode": "ro"}}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
33:[2026-11-22 17:56:06] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-av-clamav", "domain_type": 2, "direct_mount": {"mode": "ro"}}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
34:[2026-11-22 17:56:06] system/events/info {"component": "saphir-av-clamav", "module": "Api", "datetime": "2026-11-22 16:56:06.624", "description": "direct_mount enabled (mode=ro)"}
36:[2026-11-22 17:56:06] system/events/info {"component": "saphir-av-clamav", "module": "Api", "datetime": "2026-11-22 16:56:06.626", "description": "direct_mount enabled (mode=ro)"}
46:[2026-11-22 17:56:11] system/topology/my_config/request {"domain_name": "saphir-av-eset"}
47:[2026-11-22 17:56:11] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
48:[2026-11-22 17:56:11] system/events/info {"component": "saphir-av-eset", "module": "Api", "datetime": "2026-11-22 16:56:11.676", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
50:[2026-11-22 17:56:11] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-av-eset", "domain_type": 2, "direct_mount": {"mode": "ro"}}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
51:[2026-11-22 17:56:11] system/topology/my_config/request {"domain_name": "saphir-av-eset"}
52:[2026-11-22 17:56:11] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-av-eset", "domain_type": 2, "direct_mount": {"mode": "ro"}}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
53:[2026-11-22 17:56:11] system/events/info {"component": "saphir-av-eset", "module": "Api", "datetime": "2026-11-22 16:56:11.687", "description": "direct_mount enabled (mode=ro)"}
56:[2026-11-22 17:56:11] system/events/info {"component": "saphir-av-eset", "module": "Api", "datetime": "2026-11-22 16:56:11.689", "description": "direct_mount enabled (mode=ro)"}
61:[2026-11-22 17:56:26] system/topology/my_config/request {"domain_name": "saphir-gui"}
62:[2026-11-22 17:56:26] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
63:[2026-11-22 17:56:26] system/events/info {"component": "saphir-gui", "module": "Api", "datetime": "2026-11-22 16:56:27.202", "description": "the safecor_direct_mount component is ready, re-querying the direct mount configuration"}
65:[2026-11-22 17:56:26] system/topology/my_config/request {"domain_name": "saphir-gui"}
67:[2026-11-22 17:56:27] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-gui", "domain_type": 2, "direct_mount": false}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
68:[2026-11-22 17:56:27] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "saphir-gui", "domain_type": 2, "direct_mount": false}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
69:[2026-11-22 17:56:27] system/events/info {"component": "saphir-gui", "module": "Api", "datetime": "2026-11-22 16:56:27.318", "description": "direct_mount is not enabled for this domain, exiting"}
73:[2026-11-22 17:56:30] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
85:[2026-11-22 17:56:30] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
152:[2026-11-22 17:58:14] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
282:[2026-11-22 18:03:27] system/topology/my_config/request {
285:[2026-11-22 18:03:27] system/topology/my_config/response {"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "sys-usb", "domain_type": 1, "direct_mount": false}], "direct_mount_domains": ["saphir-av-clamav", "saphir-av-eset"], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
327:[2026-11-22 18:05:08] system/discover/components/response {"components": [{"id": "safecor_disk_controller", "domain_name": "sys-usb", "label": "System disk controller", "type": "core", "state": "ready"}, {"id": "safecor_input_controller", "domain_name": "sys-usb", "label": "Input controller", "type": "core", "state": "ready"}, {"id": "safecor_direct_mount", "domain_name": "sys-usb", "label": "Direct USB mount (SFTP channels)", "type": "core", "state": "ready"}]}
```

## Root cause (confirmed)

The domid boot-order race was confirmed by the Dom0 bus log
(`/var/log/safecor/messages.log`, debug mode): the two
`No domid found for domain saphir-av-clamav / saphir-av-eset, its SFTP
channel is skipped` warnings at 16:55:55.664/.670 show the controller's
one-shot domid read ran ~10 s before Dom0 wrote the business domains'
domids to xenstore (business userspace came up at 16:56:06). The
unconditional READY with 0 channels then let the business DomUs mount
`/media/usb` over sshfs, turning the missing channels into a silent
permanent I/O hang.

Fixed by issue #270 (bounded domid wait 1 s / 60 s per domain,
all-or-nothing READY after liveness verification, local persistent log
`/var/log/safecor/direct-mount.log` on sys-usb).

After installing the #270 code on the Saphir hardware, a second,
independent blocker appeared: the controller user (`svc-sys-usb-controller`,
non-root since the #253 refactor) had no access to xenstore at all
(`EACCES` on `/dev/xen/xenbus`, root-only by default), so the domids
never became readable regardless of timing. The manual workaround
`chmod 666 /dev/xen/xenbus` brought both channels up and the component
to READY; the permanent fix is issue #271 (group access granted by the
controller initd at boot).

Note: the §2 one-shot probe result "KO" was a false negative — the probe
script never subscribes to `system/discover/components/response`, and
paho-mqtt only delivers messages on subscribed topics. The probe must be
fixed before re-running §2 after the #270 fix.
