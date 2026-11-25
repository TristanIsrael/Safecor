# Run 20

The fix under test (on `version-2`, **not yet pushed**):

- **#275** — the stale-domid self-heal after a domain **self-restart** (the [run 19](run-19.md) §5 failure): the Dom0 discovery loop (`create-vchan-tunnels.py`) resolves the **live** domid from the Xen tree and writes it back to the cache only on difference (the cache is demoted to a self-healed convenience cache — ADR 0006); a SFTP channel supervisor on sys-usb re-conciles each `direct_mount` channel (start a missing one, re-pin on domid change or server death); the `restart_domain` non-forced branch always publishes a response (honest `refused` + reason for a non-self-restartable business domain) and the `forced` field is added to the API/request (default `false`); `reboot-domain.sh get_domid` uses `xl domid`.

Purpose: hardware-validate the **#275** fix: the OFF path (the run-19 failure) must converge, a single business-domain reboot must converge, and the **Saphir simultaneous-reboot case** (`sys-usb` + the two AV domains at once, order not controlled) must converge **regardless of the order**.

Preparation:
- [ ] Rebuild **`safecor-lib`** and **`safecor-core`** from the `version-2` tip (no version bump). `safecor-lib` carries the SFTP channel supervisor and the `restart_domain` contract; `safecor-core` carries `create-vchan-tunnels.py` (the self-heal) and `reboot-domain.sh` (`xl domid`) with recalculated sha512s.
- [ ] Install `safecor-lib` on **Dom0**, **sys-usb** and the business DomUs (version consistency); install `safecor-core` on **Dom0**.
- [ ] Record the installed versions on each: `apk info -v safecor-lib safecor-core 2>/dev/null`.
- [ ] **Full cold reboot in debug mode with a USB disk connected before boot** (no manual permission change).

## 1. The boot baseline (must equal run 19 §1–§4)

- [ ] The xenstore grant (#271): `ls -l /dev/xen/xenbus` → `crw-r----- root safecor` (640).
- [ ] The sandbox wrappers (#272): `ls -l /usr/lib/safecor/tmp/sandbox-*` → the two wrappers, 0755, `#!/bin/sh` + `exec /usr/bin/bwrap`, well over 512 bytes.
- [ ] The channels start on their own, one socat + one vchan server per direct_mount domain, the component `ready` on the bus (the run-19 §3 probe).
- [ ] File I/O (the objective): `df /media/usb` / `ls /media/usb` prompt, a file readable at the same path as on sys-usb, a write refused (`Read-only file system`), the watchdog remount works (the run-19 §4 checks).
- [ ] (New) The cache is consistent at boot: on Dom0, for each domain `<name>`: `xl domid <name>` equals `xenstore-read /local/domain/system/domids/<name>`.

## 2. The OFF path (run 19 §5 — the fix under test)

- [ ] On a business domain, `/media/usb` is mounted (from section 1).
- [ ] Restart sys-usb with the **API call** (non-forced, self-restart — the run-19 §5 command). Record the new domid on Dom0: `xl domid sys-usb` (it differs from the boot domid).
- [ ] While sys-usb is down / restarting, the business domain **unmounts** (the run-19 check: `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`).
- [ ] (New) The Dom0 loop self-heals: within a few seconds of the sys-usb reboot, the Dom0 log shows the domid change for sys-usb (`domid <old> → <new>`), and `xenstore-read /local/domain/system/domids/sys-usb` now equals `xl domid sys-usb`.
- [ ] (New) The vchan servers are re-pinned on the **new** domid: `ps -o pid,user,args ax | grep "vchan-socket-proxy -m server" | grep sys-usb` → the three servers (msg/input/tty) carry the **new** domid, not the boot one.
- [ ] (New) The SFTP channels survive: on sys-usb, `ps -o pid,user,args ax | grep "vchan-socket-proxy -m server" | grep -E "saphir-av"` → the two SFTP servers are still alive on the **business** domids (unchanged in this section — the AV domains did not reboot).
- [ ] After sys-usb comes back, its MQTT bridge reconnects: a business-domain message is visible on the Dom0 bus (spot check with the run-19 §3 one-shot probe).
- [ ] `safecor_direct_mount` is `ready` again (the run-19 §3 probe), the business domain **remounts** `/media/usb` automatically (no manual action), and a file read through the mount works.
- [ ] No duplicate socat/vchan listeners and no restart loop (the run-19 §5 `ps` check).

## 3. A single business-domain reboot (new coverage)

- [ ] On Dom0, reboot one AV domain through the **forced** path (the Dom0 path that updates the cache): `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_dom0('reboot')); Api().restart_domain('saphir-av-clamav', forced=True)"`.
  - After the reboot: on Dom0, `xl domid saphir-av-clamav` differs from before, and `xenstore-read /local/domain/system/domids/saphir-av-clamav` matches (the forced path wrote it).
- [ ] The SFTP supervisor re-pins the channel for that domain on its **new** domid: on sys-usb, `tail /var/log/safecor/direct-mount.log` shows the re-pin event and `ps -o pid,user,args ax | grep "vchan-socket-proxy -m server" | grep saphir-av-clamav` carries the new domid.
- [ ] The other business domain (`saphir-av-eset`) is unaffected: `/media/usb` still works (spot check: `ls /media/usb` + a file read).
- [ ] (New) The **non-forced** `restart_domain` on a business domain is **refused** with a reason (a business domain cannot self-restart through this path): the API response is published and carries `refused` + reason; the domain is not restarted.

## 4. The Saphir simultaneous reboot (order not controlled — the fix under test)

- [ ] From Dom0 (the API), trigger the three reboots **at once, with no ordering and no wait in between**: `restart_domain('sys-usb')` (non-forced, self-restart) + `restart_domain('saphir-av-clamav', forced=True)` + `restart_domain('saphir-av-eset', forced=True)`.
- [ ] All three come back with **new** domids: on Dom0, `xl domid <name>` for each (all differ from the boot domids).
- [ ] (New) The cache self-heals for **all** of them: for each `<name>` in `sys-usb saphir-av-clamav saphir-av-eset`, `xenstore-read /local/domain/system/domids/<name>` equals `xl domid <name>`; the Dom0 log shows the `domid <old> → <new>` lines (the AV ones may already be fresh from the forced path — the sys-usb one is the self-heal).
- [ ] Full convergence, **no manual action, any order**:
  - [ ] The sys-usb vchan servers (msg/input/tty) carry the **new** sys-usb domid (Dom0 `ps`).
  - [ ] The two SFTP channels are (re)pinned on the **new** AV domids (sys-usb `ps` + `direct-mount.log`).
  - [ ] `safecor_direct_mount` is `ready` again (the run-19 §3 probe).
  - [ ] **Both** business DomUs remount `/media/usb` and a file read through the mount works on each.
  - [ ] A business-domain message is visible on the Dom0 bus (the MQTT bridges reconnected).
- [ ] No duplicate listeners, no restart loop, no stuck component state (`grep -n "safecor_direct_mount" /var/log/safecor/messages.log | tail -20` on Dom0).

## 5. Regressions

- [ ] The local brokers stay connected across all the reboots above: a business-domain message is visible on the Dom0 bus after each.
- [ ] Messaging, inputs and GUI still work (spot check: the mouse moves on the GUI domain, the Saphir app displays, its messages are visible on the bus).
- [ ] The debug tty (the run-14 regression, still open in `test-channels-migration.md`): works in debug mode (type on the USB serial terminal, it appears on the Dom0 console). If KO, it stays open with its dedicated diagnosis — it does not block the direct-mount closure.
- [ ] The forced path is unchanged: `reboot-domain.sh` still writes the cache (`get_domid` now via `xl domid`); the run-19 boot behavior is identical.

## If everything is green

Mark **#275** In review (Kanban) — implementation done, hardware-validated. Then: close **#262** (re-scoped by #275 — its forced-path fix is superseded by the self-heal), and close **#273**, **#271**, **#272**, **#274** as validated (all their run-19 §1–§4 checks are green); check the "file read on a USB storage from a Domain" objective in `test-channels-migration.md` (run 19 §4 green, run 20 §4 covers the restart case); update `docs/project-status.md`; close **#256** (and **#253**, **#260** if not already).

## Diagnostics (only if not green)

- Dom0, the self-heal: `grep -n "domid" /var/log/safecor/messages.log | tail -20` (the `domid <old> → <new>` lines), the cache: `xenstore-ls /local/domain/system/domids`, the live domids: `xl domid <name>`.
- Dom0, the vchan servers: `ps -o pid,user,args ax | grep "vchan-socket-proxy -m server" | grep -v grep` (which domid each carries).
- sys-usb, the SFTP supervisor: `tail -30 /var/log/safecor/direct-mount.log` (the re-pin events, the liveness checks) and `ps -o pid,user,args ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep`.
- sys-usb, the MQTT bridge: `tail -20 /var/log/messages | grep mosquitto` (the bridge reconnect), and the run-19 §3 probe from a business domain.
