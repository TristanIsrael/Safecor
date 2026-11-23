# Run 18

> **Result (2026-11-23): NOT GREEN.** §1 (the xenstore grant, #271) passed on both cold boots; §3 failed — the channels never started because the controller's one-shot `my_config` query consumed a **filtered** response (the answer to the local direct-mount manager's own request): the component went READY **with zero channels** (the "No domain with direct_mount in the topology" signature). Root cause confirmed in the section below; fixed in **#273** (`6b35770`, pushed) and to be hardware-validated in [run 19](run-19.md) — which is also the first hardware pass for #272 (the wrappers were never exercised here).

Purpose: validate on the Saphir hardware the two fixes that closed the [run 17](run-17.md) blockers — on a **clean reboot with no manual `chmod`/`chgrp` anywhere** — and complete the run-17 sheet (the file I/O §4, the OFF path §6, the untested regressions §8).

The fixes under test (both on `version-2`, both reviewed and committed, both **not yet pushed**):

- **#271** (`dc9bc21`) — the controller initd grants the `safecor` group read access to `/dev/xen/xenbus` at boot (`chgrp safecor` + `chmod 640`, fallback `660` if a read-only test as `svc-sys-usb-controller` fails; world access excluded per design rule #10): the controller (non-root since the #253 refactor) could not read the DomU domids at all (`EACCES`), so the SFTP channels never started at boot.
- **#272** (`59d67a5`) — a per-domain sandbox wrapper script in `/usr/lib/safecor/tmp` keeps the socat EXEC address under the parser's 512-byte limit: the full bwrap command (781-char EXEC address on Alpine 3.24) was rejected at parse time, so every SFTP session died at birth and the business DomUs' `/media/usb` sshfs hung on any I/O.

Preparation:
- [x] Rebuild **`safecor-lib`** and **`safecor-sys-usb`** from the `version-2` tip (`59d67a5`; no version bump). `safecor-lib` carries the wrapper logic (`write_sandbox_wrapper`, the absolute `bwrap` in `SandboxContext`, the short socat address); `safecor-sys-usb` carries the initd (the xenstore block + the wrapper dir block) and the recomputed sha512s.
- [x] Install `safecor-lib` on the **Dom0**, **sys-usb** and the business DomUs; install `safecor-sys-usb` on **sys-usb**.
- [x] Record the installed versions on each of the above: `apk info -v safecor-lib safecor-sys-usb 2>/dev/null`.
- [x] **Full cold reboot in debug mode with a USB disk connected before boot and no manual permission change** (no `chmod`/`chgrp` on `/dev/xen/xenbus` or anywhere else — the initd blocks must do it).

## 1. The xenstore grant at boot (#271, sys-usb)

- [x] The device is group-accessible by `safecor` only (never world): `ls -l /dev/xen/xenbus` → `crw-r----- root safecor` (640), or `crw-rw-----` (660) if the fallback was needed; `stat -c '%a %U:%G' /dev/xen/xenbus` confirms.
  - OK
- [x] The controller user can read xenstore: `su -s /bin/sh svc-sys-usb-controller -c "xenstore-read /"` → a JSON key list, no `EACCES`.
  - OK but there is a small error at the end
```
su -s /bin/sh svc-sys-usb-controller -c "xenstore-ls /local/domain/system"
screen_size = "800,1280"
screen_rotation = "90"
debug_on = "1"
domids = ""
 sys-usb = "1"
 saphir-gui = "2"
 saphir-av-clamav = "3"
 saphir-av-eset = "4"
input-focus = "saphir-gui"
vchan = ""
 sys-usb = ""
  msg = ""
   ring-ref = "8"
   event-channel = "63"
  input = ""
   ring-ref = "9"
   event-channel = "64"
  tty = ""
   ring-ref = "10"
   event-channel = "65"
 saphir-gui = ""
  msg = ""
   ring-ref:

xenstore-ls: xs_directory (/local/domain/system/vchan/saphir-gui/msg/ring-ref): Permission denied
```

## 2. The sandbox wrapper dir and the wrappers (#272, sys-usb)

- [x] The directory is created at boot with the expected ownership: `ls -ld /usr/lib/safecor/tmp` → `drwxrwx--- root safecor`.
  - OK
- [x] After the channels start (section 3), one wrapper per `direct_mount` domain: `ls -l /usr/lib/safecor/tmp/sandbox-*` → `sandbox-saphir-av-clamav` and `sandbox-saphir-av-eset`, mode 0755, and no other `sandbox-*` (the initd removed the stale ones from a previous boot).
  - The folder is empty
- [ ] A wrapper is the `#!/bin/sh` + single `exec` script, the first argument the absolute bwrap path: `head -1 /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → `#!/bin/sh`, and the second line starts with `exec /usr/bin/bwrap `.
- [ ] The long command really moved to the file (the socat address is what is short now): `wc -c /usr/lib/safecor/tmp/sandbox-saphir-av-clamav` → well over 512 bytes (the full bwrap command line).

## 3. The channels come up on their own, the component READY (sys-usb)

- [x] Per domain `<name>` (`saphir-av-clamav`, `saphir-av-eset`), one socat with the **short** address and one vchan server, no duplicates, no restart loop:
  ```
  ps -o pid,user,args ax | grep -E "socat UNIX-LISTEN|vchan-socket-proxy -m server" | grep -v grep
  ```
  - Expected, per domain: `socat UNIX-LISTEN:/var/run/safecor/direct-mount/vchan-<name>.sock,fork EXEC:"/usr/lib/safecor/tmp/sandbox-<name>"` and `vchan-socket-proxy -m server <domid> /local/domain/system/vchan/<name>/sftp /var/run/safecor/direct-mount/vchan-<name>.sock`.
  - KO: any `EXEC:"bwrap` (the old long address is back) or no line at all (the channels did not start — check `/var/log/safecor/direct-mount.log`, the diagnostics below).
  -> KO : no `EXEC:"bwrap`
- [x] The per-domain log is clean: `cat /var/run/safecor/direct-mount/vchan-<name>.log` — no `E address "EXEC:"…` line (the run-17 failure signature).
  - KO : The directory is empty
- [x] The local persistent log shows the start, the liveness verification and the READY: `grep -E "SFTP channel|READY" /var/log/safecor/direct-mount.log | tail -10` → `Starting the SFTP channel for <name> (domid <n>, mode ro)` per domain, then `All SFTP channels started and verified alive — component READY`.
  - KO : not started
```
/etc/init.d/direct-mount status
 * status: crashed
```
- [ ] The component is `ready` on the bus — on a business domain, with the **fixed** one-shot probe (the run-17 §2 probe never subscribed to the response topic, so its "NOT FOUND (timeout)" was a false negative):
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

## 4. File I/O through the mount (run 17 §4, business DomUs)

- [ ] The run-17 hang is gone: `df /media/usb` and `ls /media/usb` return promptly on a business domain.
- [ ] `ro` domain: a file from the USB disk connected before boot is readable at the same path as on sys-usb: `cat /media/usb/<disk>/<file>`.
- [ ] `ro` domain: a write through the mount is **refused**: `touch /media/usb/<disk>/x` → `Read-only file system`.
- [ ] **Watchdog remount**: on a business domain, `fusermount -u /media/usb`; within a few seconds `mount | grep /media/usb` is back and the manager log shows `the sshfs process terminated, remounting`.
- [ ] (Optional) a direct `sftp` session through the vchan lists the files: `sftp -o "ProxyCommand=/usr/local/bin/vchan-sftp" none@localhost` → `ls` (the run-17 §7 check).

## 5. The OFF path (run 17 §6, sys-usb restart ⇒ unmount, then remount)

- [ ] On a business domain, `/media/usb` is mounted (from section 4).
- [ ] Restart sys-usb: `python3 -c "import sys; sys.path.insert(0,'/usr/lib/safecor'); from safecor import Api, MqttFactory; Api().start(MqttFactory.create_mqtt_client_domu('reboot')); Api().restart_domain('sys-usb')"` (or `xl reboot sys-usb`).
- [ ] While sys-usb is down / restarting, the business domain **unmounts** (the controller published `OFF`): `mount | grep /media/usb` → gone; the manager log shows `the direct mount component is OFF, unmounting`.
- [ ] After sys-usb comes back and its `safecor_direct_mount` is `READY` again, the business domain **remounts** automatically (no manual action).
- [ ] No duplicate socat/vchan listeners and no restart loop after the restart (idempotent `start_sftp_channel`): re-run the section-3 `ps` check (one socat + one vchan server per domain).
- [ ] The stale wrappers were removed by the initd at the sys-usb boot and rewritten by the controller: re-run the section-2 checks.

## 6. Regressions (run 17 §8 + the five objectives)

- [ ] The local brokers stay connected across the reboots tested above (including the sys-usb restart): a business-domain message is visible on the Dom0 bus.
- [ ] Messaging, inputs and GUI still work after the sys-usb restart (spot check: the mouse moves on the GUI domain, the Saphir app displays, its messages are visible on the bus).
- [ ] The debug tty (the run-14 regression, still open in `test-channels-migration.md`): works in debug mode (type on the USB serial terminal, it appears on the Dom0 console). If KO, it stays open with its dedicated diagnosis — it does not block the direct-mount closure.

## Root cause (confirmed): the my_config response race

The local persistent log on sys-usb:
```
2026-11-23 21:02:29 No domain with direct_mount in the topology
2026-11-23 21:02:29 Direct USB mount component state -> ready
```

**§1 passed**: the initd xenstore block works at boot — the device is
group-accessible by `safecor` and the controller user reads the domids.
(The trailing `Permission denied` on
`/local/domain/system/vchan/saphir-gui/msg/ring-ref` is **expected**:
the vchan `ring-ref` nodes carry per-domain grants — owner domain and
Dom0 only — and sys-usb is not granted read on another domain's channel.
This is the least-privilege behavior #261 will formalize, not a defect.)

The channels never started because the controller's one-shot my_config
query **consumed the wrong response**. Evidence chain:

1. Two processes on sys-usb query my_config at boot: the **controller**
   publishes `{}` (no filter → Dom0 answers with the **full** topology)
   and the **local `direct-mount` manager** (the `safecor-domu-base`
   service, installed on sys-usb as a dependency) publishes
   `{"domain_name": "sys-usb"}` (→ Dom0 answers with a response filtered
   to `domains: [sys-usb]`). Both requests are visible in the run-17 bus
   log at 17:55:55; both responses are published on the **shared**
   `system/topology/my_config/response` topic.
2. The controller's accept filter
   (`__accept_my_config_response`) accepts any response whose `domains`
   list contains "sys-usb" — its rationale ("a response filtered for
   another domain never lists sys-usb itself") is wrong for the response
   filtered **for sys-usb itself**, which does list it.
3. `parse_direct_mount_domains` reads the (possibly filtered) `domains`
   list: a `domains: [sys-usb]` payload parses to an **empty** pair list
   (sys-usb has no direct_mount).
4. At this boot the filtered response (the answer to the manager's
   request) reached the controller before its own full-topology answer:
   the filter accepted it, the pairs list was empty, the channel thread
   exited early ("No domain with direct_mount in the topology") and the
   component went READY **with zero channels** — by design for a
   topology with no direct_mount domains, which is why nothing else was
   logged. At run 17 the race was won the other way (the full answer
   first), which is why the channels started there.

Consequences on this boot: no wrapper, no socat / vchan-socket-proxy,
empty per-domain log; the business DomUs' `safecor_direct_mount` is
`ready` with no SFTP channel behind it, so their `/media/usb` sshfs
mounts but hangs on I/O (the run-17 symptom) — section 4 is not
testable until the fix is in.

Note: `direct-mount status: crashed` on **sys-usb** is a benign openrc
quirk — sys-usb is not a direct_mount domain, so its short-lived manager
queries my_config, sees `direct_mount: false` and **exits by design**;
openrc then reports the exited pidfile as "crashed". Not a defect.

**Fix — implemented and pushed** (#273, `6b35770`): the controller's
accept filter is tightened — a response is only the full topology when the
`domains` list contains `sys-usb` **and** every name of the
`direct_mount_domains` field (that field is computed globally in
`create_my_config`, never filtered, so a filtered-for-sys-usb response
always misses the direct-mount domains and is rejected; the degenerate
no-direct_mount topology is unaffected). Controller-side only: no protocol
change, no Dom0 change, no impact on the business DomUs. The manager's own
filter (ignore a response that does not list its own domain) is already
correct. Hardware validation: [run 19](run-19.md), section 3 (including the
Dom0 bus-log check of the two responses' order).

Optional confirmation on **Dom0** (the order of the two responses at
21:02:29):
```
grep -n "my_config" /var/log/safecor/messages.log | tail -8
```

## If everything is green

Push `version-2` (on explicit user request), close **#271** and **#272** as validated (Kanban: In review → Done), close **#256** (and **#253** as validated, plus **#260**, **#262** if not already), check the "file read on a USB storage from a Domain" objective in `test-channels-migration.md`, update `docs/project-status.md`, and move to the second pass (Phase F: #259, #261).

## Diagnostics (only if not green)

- sys-usb, the channel lifecycle: `tail -30 /var/log/safecor/direct-mount.log` — the ERROR events name the failing domain and the reason (domid timeout, helper error, liveness verification).
- sys-usb, the per-domain socat log: `cat /var/run/safecor/direct-mount/vchan-<name>.log` — an `E address "EXEC:"…` line means the #272 signature is back (check the wrapper: `ls -l /usr/lib/safecor/tmp/sandbox-*`, `head -1`, and that the socat command line carries the short address).
- sys-usb, the initd: `rc-status safecor-sys-usb-controller` and `grep -iE "sys-usb-controller" /var/log/messages` (did the start run, in which order).
- Dom0, the component state history: `grep -n "safecor_direct_mount" /var/log/safecor/messages.log | tail -20`.
