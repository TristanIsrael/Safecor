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

- [x] After the channels start (section 3), one wrapper per `direct_mount` domain: `ls -l /usr/lib/safecor/tmp/sandbox-*` → `sandbox-saphir-av-clamav` and `sandbox-saphir-av-eset`, mode 0755, and no other `sandbox-*`.
  - OK
- [x] A wrapper is the `#!/bin/sh` + single `exec` script, the first argument the absolute bwrap path: `head -1 /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → `#!/bin/sh`, and the second line starts with `exec /usr/bin/bwrap `.
  - OK
- [x] The long command really moved to the file (the socat address is what is short now): `wc -c /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → well over 512 bytes (the full bwrap command line).
  - 799 chars

## 3. The channels come up on their own, the component READY (sys-usb) — the #273 check

- [x] The run-18 signature is gone: `grep "No domain with direct_mount" /var/log/safecor/direct-mount.log` → **no match**.
  - OK
- [x] The local persistent log shows the start, the liveness verification and the READY: `grep -E "SFTP channel|READY" /var/log/safecor/direct-mount.log | tail -10` → `Starting the SFTP channel for <name> (domid <n>, mode ro)` per domain, then `All SFTP channels started and verified alive — component READY`.
  - OK
- [x] Per domain `<name>` (`saphir-av-clamav`, `saphir-av-eset`), one socat with the **short** address and one vchan server, no duplicates, no restart loop:
  ```
  ps -o pid,user,args ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep
  ```
  - Expected, per domain: `socat UNIX-LISTEN:/var/run/safecor/direct-mount/vchan-<name>.sock,fork EXEC:"/usr/lib/safecor/tmp/sandbox-<name>"` and `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/direct-mount/vchan-<name>.sock`.
  - KO: any `EXEC:"bwrap` (the old long address is back) or no line at all (the channels did not start — check `/var/log/safecor/direct-mount.log`, the diagnostics below).
  -> OK
- [x] The per-domain log is clean: `cat /var/run/safecor/direct-mount/vchan-<name>.log` — no `E address "EXEC:"…` line (the run-17 failure signature).
  - They are both empty
- [x] The component is `ready` on the bus — on a business domain, with the one-shot probe (subscribes to the response topic before the request — the run-17 false negative, fixed in the run-18 sheet):
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

- [x] The run-17 hang is gone: `df /media/usb` and `ls /media/usb` return promptly on a business domain.
  - OK
- [x] `ro` domain: a file from the USB disk connected before boot is readable at the same path as on sys-usb: `cat /media/usb/<disk>/<file>`.
  - OK
- [x] `ro` domain: a write through the mount is **refused**: `touch /media/usb/<disk>/x` → `Read-only file system`.
  - OK
- [x] **Watchdog remount**: on a business domain, `fusermount -u /media/usb`; within a few seconds `mount | grep /media/usb` is back and the manager log shows `the sshfs process terminated, remounting`.
  - OK
- [x] (Optional) a direct `sftp` session through the vchan lists the files: `sftp -o "ProxyCommand=/usr/local/bin/vchan-sftp" none@localhost` → `ls`.

## 5. The OFF path (sys-usb restart ⇒ unmount, then remount)

- [x] On a business domain, `/media/usb` is mounted (from section 4).
- [x] Restart sys-usb: `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_domu('reboot')); Api().restart_domain('sys-usb')"` (or `xl reboot sys-usb`).
  - I used the API call
- [x] While sys-usb is down / restarting, the business domain **unmounts** (the controller published `OFF`): `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`.
  - OK
- [x] After sys-usb comes back and its `safecor_direct_mount` is `READY` again, the business domain **remounts** automatically (no manual action).
  - `safecor_direct_mount` is never `READY` again. No message comes up from `sys-usb`
  - The last messages in `/var/log/messages` are:
```
2026-11-24 17:23:01 notice mosquitto[3761]: 1795540981: Client safecor-sys-usb-bridge [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-24 17:23:01 err Safecor/Input[4315]: proxy[4315]: Connection with inputs socket lost
```
  - In `/var/log/safecor/system.log`:
```
2026-11-24 17:23:01 err Safecor/Input[4315]: proxy[4315]: Connection with inputs socket lost
```
- [x] No duplicate socat/vchan listeners and no restart loop after the restart (idempotent `start_sftp_channel`): re-run the section-3 `ps` check (one socat + one vchan server per domain).
  - No duplicates but `ps ax | grep sys-usb` shows:
```
4741 svc-vcha  0:00 vchan-socket-proxy -m server 1 /local/domain/system/vchan/sys-usb/msg /tmp/mqtt-sys-usb.sock
 4742 svc-vcha  0:00 vchan-socket-proxy -m server 1 /local/domain/system/vchan/sys-usb/input /var/run/safecor/sys-usb-input.sock
 4743 svc-vcha  0:00 vchan-socket-proxy -m server 1 /local/domain/system/vchan/sys-usb/tty /var/run/safecor/sys-usb-tty.sock
```
  , whereas `xl domid sys-usb` returns 5.
- [ ] The stale wrappers were removed by the initd at the sys-usb boot and rewritten by the controller: re-run the section-2 checks.

>>> Test run stopped here

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

## Resolution (run NOT green — stopped at §5)

**Verdict: NOT GREEN.** Sections 1–4 are green; the run stopped at section 5 (the OFF path): after the `sys-usb` restart, `safecor_direct_mount` never reached `ready` again and the business DomUs never remounted `/media/usb`.

- **§1 (the xenstore grant, #271):** OK — spot check: `/dev/xen/xenbus` is `crw-r----- root safecor` (640); validated at run 18.
- **§2 (the sandbox wrappers, #272 — first hardware pass):** OK — the two wrappers are `#!/bin/sh` + single `exec` scripts, 799 chars (the full bwrap command line in the file, the socat address is short).
- **§3 (the channels, the #273 check):** OK — the run-18 signature is gone, the channels start on their own, the component is `ready` on the bus, the per-domain logs are empty (clean). The last §3 check (the bus-log order of the two `my_config` responses) is pending but non-blocking: the channels starting at all is already evidence the new accept filter behaves.
- **§4 (file I/O — the objective):** OK — `df`/`ls` prompt, a file readable at the same path as on sys-usb, a write refused (`Read-only file system`), the watchdog remount works.
- **§5 (the OFF path):** **KO** — see below.
- **§6 (regressions):** not reached (the run stopped at §5).

### The §5 failure: the domid is stale after a self-restart

Restart command used: the API call `Api().restart_domain('sys-usb')` (the default, **non-forced** — this is a **self-restart**: the controller reboots sys-usb itself via `doas /sbin/reboot`).

Observed on Dom0 after the reboot:

- `xl domid sys-usb` → **5** (the domain was destroyed and recreated: new domid).
- The three Dom0 vchan servers for sys-usb (msg/input/tty) still run with **domid 1** (`ps`: `vchan-socket-proxy -m server 1 /local/domain/system/vchan/sys-usb/…` for all three).
- Consequences: no MQTT comes up from sys-usb (its local bridge's upstream vchan points to rings that no longer exist), the controller's `safecor_direct_mount` never becomes `ready` again, and the business DomUs never remount.

The unmount half worked: while sys-usb was down, the business domain unmounted (`the direct mount component is OFF, unmounting`). No duplicate listeners, no restart loop.

### Root cause

The non-forced `restart_domain` is a **self-restart** (`docs/development/protocol.md`: "`forced`: if true, the restart is forced in Dom0, otherwise the Domain restarts itself"). A self-reboot destroys/recreates the Xen domain (domid 1 → 5) but **a DomU cannot update the Dom0 domid cache** `/local/domain/system/domids/<name>` — only the *forced*, Dom0 path (`reboot-domain.sh`) writes it. The Dom0 discovery loop (`create-vchan-tunnels.py`) **trusts that stale cache**, so the vchan servers stay pinned to the old domid. The business-domain SFTP vchan client reads the same cache at remount, and the SFTP server on sys-usb is pinned to the *business* domid and only (re)started at sys-usb's boot. Pre-#261 the cache is also DomU-writable (`set-xenstore-permissions.sh` grants `b` on all of `/local/domain/system`).

Note the asymmetry with the earlier sections: at boot the cache is written by the Dom0 path and is correct; only the *self-restart* path leaves it stale — which is why the #262 fix (the `reboot-domain.sh` polling) is correct but did not prevent this failure.

### Fix (tracked as #275)

One issue, a self-healing fix that is **order-independent** (the Saphir case: `sys-usb` + `saphir-av-clamav` + `saphir-av-eset` rebooting simultaneously, order not controlled):

1. **Dom0 loop self-heal + cache write-back** (`create-vchan-tunnels.py`): resolve the **live** domid from the Xen tree `/local/domain/<N>/name` (hypervisor-maintained, unforgeable), use it for the vchan servers, write it back to the cache only on difference (≤1 s convergence), log `domid <old> → <new>`. The cache is demoted from "source of truth" to a self-healed convenience cache (**ADR 0006**).
2. **SFTP channel supervisor** (`_sys_usb_controller.py`): re-concile each `direct_mount` channel against the (now-fresh) cache — start a missing channel, re-pin a channel whose business domid changed or whose server died (reuses the idempotent doas helper + liveness check).
3. **`restart_domain` contract** (`_dom0_controller.py`, `_api.py`, `_request_factory.py`): the non-forced branch always publishes a response (an honest `refused` + reason for a non-self-restartable business domain); the `forced` field is added to the API/request (default `false`).
4. **Hardening**: `reboot-domain.sh get_domid` → `xl domid "$1"` (consistency with the `start-*.sh` scripts).

Hardware re-validation: [run 20](run-20.md).
