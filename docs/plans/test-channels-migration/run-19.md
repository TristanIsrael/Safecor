# Run 19

Purpose: hardware-validate the **#273** fix (the `my_config` response race, root-caused in [run 18](run-18.md)) on the Saphir hardware, on a **clean cold reboot with no manual `chmod`/`chgrp` anywhere**. This is also the **first hardware pass for #272**: run 18's channels never started (the race), so the per-domain sandbox wrappers were never exercised.

The fix under test (on `version-2`, **pushed**):

- **#273** (`6b35770`) — the controller's accept filter now rejects a `my_config` response filtered for sys-usb: it only accepts a response whose `domains` contains `sys-usb` **and** every name of the `direct_mount_domains` field (that field is computed globally in `create_my_config`, never filtered per request). The run-18 failure — the filtered-for-sys-usb answer consumed by the controller, the empty pair list, READY with zero channels — is what this run must not reproduce.

The run-18 signature (this run must not show it): `No domain with direct_mount in the topology` + `Direct USB mount component state -> ready` with no channels.

Preparation:
- [x] Rebuild **`safecor-lib`** only, from the `version-2` tip (`6b35770`; no version bump). #273 touches `_sys_usb_controller.py`, its tests and the component doc: no initd, no package resources, so `safecor-sys-usb` is unchanged and no APKBUILD checksums are recalculated.
- [x] Install `safecor-lib` on **Dom0** and **sys-usb** (the controller runs on sys-usb); on the business DomUs as well for version consistency.
- [x] Record the installed version on each: `apk info -v safecor-lib 2>/dev/null`.
- [x] **Full cold reboot in debug mode with a USB disk connected before boot and no manual permission change** (no `chmod`/`chgrp` on `/dev/xen/xenbus` or anywhere else — the initd blocks must do it).

## 1. The xenstore grant at boot (#271) — skipped, validated in run 18

- [x] (Optional spot check, sys-usb) `ls -l /dev/xen/xenbus` → `crw-r----- root safecor` (640), or `crw-rw-----` (660) if the fallback was needed.
  - OK

## 2. The sandbox wrappers (#272, sys-usb) — first hardware pass

- [ ] After the channels start (section 3), one wrapper per `direct_mount` domain: `ls -l /usr/lib/safecor/tmp/sandbox-*` → `sandbox-saphir-av-clamav` and `sandbox-saphir-av-eset`, mode 0755, and no other `sandbox-*`.
- [ ] A wrapper is the `#!/bin/sh` + single `exec` script, the first argument the absolute bwrap path: `head -1 /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → `#!/bin/sh`, and the second line starts with `exec /usr/bin/bwrap `.
- [ ] The long command really moved to the file (the socat address is what is short now): `wc -c /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → well over 512 bytes (the full bwrap command line).

## 3. The channels come up on their own, the component READY (sys-usb) — the #273 check

- [ ] The run-18 signature is gone: `grep "No domain with direct_mount" /var/log/safecor/direct-mount.log` → **no match**.
- [ ] The local persistent log shows the start, the liveness verification and the READY: `grep -E "SFTP channel|READY" /var/log/safecor/direct-mount.log | tail -10` → `Starting the SFTP channel for <name> (domid <n>, mode ro)` per domain, then `All SFTP channels started and verified alive — component READY`.
- [ ] Per domain `<name>` (`saphir-av-clamav`, `saphir-av-eset`), one socat with the **short** address and one vchan server, no duplicates, no restart loop:
  ```
  ps -o pid,user,args ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep
  ```
  - Expected, per domain: `socat UNIX-LISTEN:/var/run/safecor/direct-mount/vchan-<name>.sock,fork EXEC:"/usr/lib/safecor/tmp/sandbox-<name>"` and `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/direct-mount/vchan-<name>.sock`.
  - KO: any `EXEC:"bwrap` (the old long address is back) or no line at all (the channels did not start — check `/var/log/safecor/direct-mount.log`, the diagnostics below).
- [ ] The per-domain log is clean: `cat /var/run/safecor/direct-mount/vchan-<name>.log` — no `E address "EXEC:"…` line (the run-17 failure signature).
- [ ] The component is `ready` on the bus — on a business domain, with the one-shot probe (subscribes to the response topic before the request — the run-17 false negative, fixed in the run-18 sheet):
  ```
  python3 - <<'PY'
  import sys, threading, time
  sys.path.insert(0, "/usr/lib/safecor")
  from safecor import Api, MqttFactory, Topics, Constants
  done, result = threading.Event(), {}
  def on_message(topic, payload):
    if topic == f"{Topics.DISCOVER_COMPONENTS}/response":
      for c in payload.get("components", []):
        if c.get("id") == Constants.SAFECOR_DIRECT_MOUNT:
          result["state"] = c.get("state"); done.set()
  def on_ready():
    Api().subscribe(f"{Topics.DISCOVER_COMPONENTS}/response")
    time.sleep(0.5)  # let the broker process the SUBSCRIBE before the request
    Api().discover_components()
  Api().add_ready_callback(on_ready); Api().add_message_callback(on_message)
  Api().start(MqttFactory.create_mqtt_client_domu("component-check"))
  done.wait(timeout=15)
  print("safecor_direct_mount state:", result.get("state", "NOT FOUND (timeout)"))
    PY
  ```
  - Expected: `safecor_direct_mount state: ready`.
- [ ] **Proof the race was settled correctly** (Dom0, the bus log in debug mode mirrors every message): `grep -n "my_config" /var/log/safecor/messages.log | tail -8` — at boot both responses are visible (the full topology, and the filtered one with `domains: ["sys-usb"]`). The channels started, so the controller accepted the **full** one. Decisive case: if the filtered response is timestamped **before** the full one, the old filter would have accepted it — channels starting anyway is direct evidence the new filter rejected it.

## 4. File I/O through the mount (business DomUs) — the objective

- [ ] The run-17 hang is gone: `df /media/usb` and `ls /media/usb` return promptly on a business domain.
- [ ] `ro` domain: a file from the USB disk connected before boot is readable at the same path as on sys-usb: `cat /media/usb/<disk>/<file>`.
- [ ] `ro` domain: a write through the mount is **refused**: `touch /media/usb/<disk>/x` → `Read-only file system`.
- [ ] **Watchdog remount**: on a business domain, `fusermount -u /media/usb`; within a few seconds `mount | grep /media/usb` is back and the manager log shows `the sshfs process terminated, remounting`.
- [ ] (Optional) a direct `sftp` session through the vchan lists the files: `sftp -o "ProxyCommand=/usr/local/bin/vchan-sftp" none@localhost` → `ls`.

## 5. The OFF path (sys-usb restart ⇒ unmount, then remount)

- [ ] On a business domain, `/media/usb` is mounted (from section 4).
- [ ] Restart sys-usb: `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_domu('reboot')); Api().restart_domain('sys-usb')"` (or `xl reboot sys-usb`).
- [ ] While sys-usb is down / restarting, the business domain **unmounts** (the controller published `OFF`): `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`.
- [ ] After sys-usb comes back and its `safecor_direct_mount` is `READY` again, the business domain **remounts** automatically (no manual action).
- [ ] No duplicate socat/vchan listeners and no restart loop after the restart (idempotent `start_sftp_channel`): re-run the section-3 `ps` check (one socat + one vchan server per domain).
- [ ] The stale wrappers were removed by the initd at the sys-usb boot and rewritten by the controller: re-run the section-2 checks.

## 6. Regressions

- [ ] The local brokers stay connected across the reboots tested above (including the sys-usb restart): a business-domain message is visible on the Dom0 bus.
- [ ] Messaging, inputs and GUI still work after the sys-usb restart (spot check: the mouse moves on the GUI domain, the Saphir app displays, its messages are visible on the bus).
- [ ] The debug tty (the run-14 regression, still open in `test-channels-migration.md`): works in debug mode (type on the USB serial terminal, it appears on the Dom0 console). If KO, it stays open with its dedicated diagnosis — it does not block the direct-mount closure.

## If everything is green

Mark **#273** validated (Kanban In review → Done), close **#271** and **#272** as validated, close **#256** (and **#253** as validated, plus **#260**, **#262** if not already), check the "file read on a USB storage from a Domain" objective in `test-channels-migration.md`, update `docs/project-status.md`, and move to the second pass (Phase F: #259, #261).

## Diagnostics (only if not green)

- sys-usb, the channel lifecycle: `tail -30 /var/log/safecor/direct-mount.log` — the ERROR events name the failing domain and the reason (domid timeout, helper error, liveness verification). A `No domain with direct_mount in the topology` line means the #273 signature is back (check the installed `safecor-lib` version: `apk info -v safecor-lib` must be the one built from `6b35770`).
- sys-usb, the per-domain socat log: `cat /var/run/safecor/direct-mount/vchan-<name>.log` — an `E address "EXEC:"…` line means the #272 signature is back (check the wrapper: `ls -l /usr/lib/safecor/tmp/sandbox-*`, `head -1`, and that the socat command line carries the short address).
- sys-usb, the initd: `rc-status safecor-sys-usb-controller` and `grep -iE "sys-usb-controller" /var/log/messages` (did the start run, in which order).
- Dom0, the component state history: `grep -n "safecor_direct_mount" /var/log/safecor/messages.log | tail -20`; the my_config exchange order: `grep -n "my_config" /var/log/safecor/messages.log | tail -8`.
