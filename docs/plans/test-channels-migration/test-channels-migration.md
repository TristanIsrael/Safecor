# Validation tests for the migration from channels to pvchan

## Objectives

The objectives are:

- [x] Validate the channels replacement for the messaging on all Domains (runs 13, 14 — #258)
- [x] Validate the channels replacement for the inputs on sys-usb (runs 13, 14)
- [ ] Validate the channels replacement for the debugging tty on sys-usb (OK at run 13, regression at run 14 — to be fixed and re-validated)
- [ ] Validate the file read on a USB storage from a Domain (the sshfs direct mount — #260)
- [x] Validate the GUI display (runs 13, 14)

The remaining work and the planned sequence are in [finalization-plan.md](finalization-plan.md).

## Runs

The runs are described in their own file in the same directory as this file. Runs 15–17 validated the direct-mount redesign in sequence ([run 15](run-15.md), [run 16](run-16.md), [run 17](run-17.md)); run 17 closed as **NOT GREEN** (the xenstore `EACCES` — #271 — and the socat 512-byte limit — #272). [Run 18](run-18.md) was the next hardware pass with those two fixes: **NOT GREEN** — #271 validated at boot, but the channels never started because of a new root-caused bug, the `my_config` response race (#273). [Run 19](run-19.md) is the follow-up: the #273 fix, and the first hardware pass for #272 — **NOT GREEN** (§1–§4 green: #273 and #272 validated, the file-I/O objective met; but the OFF path §5 failed: after the `sys-usb` self-restart the Dom0 domid cache went stale and the vchan servers stayed on the old domid — #275, the re-scoped #262). [Run 20](run-20.md) hardware-validates the #275 self-heal: the OFF path, a single business reboot, and the Saphir simultaneous reboot (order not controlled).

## Run 14 resolutions

Run 14 validated #258 (the DomU local MQTT broker) and #264 (the `/etc` permissions on the DomUs, with the run-12 cascades: the GUI input and the API reboot), and exposed two findings.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | The debug tty does not work anymore (regression — it worked at run 13): all the components are present (Dom0: the `vchan-socket-proxy` server, `create-tty-tunnel.sh`, `create-tty-terminal.sh`, `getty` on `/var/run/safecor/tty-admin`; sys-usb: the `tty` vchan client and `socat /dev/ttyUSB0`), so the break is in the chain assembly, probably related to the run-13→14 changes (mosquitto/socat apk dependencies, `safecor-domu-base` made a dependency of `safecor-sys-usb`, the duplicated `setup-vchan` removed from `safecor-sys-usb`). | Diagnose the chain on real hardware (which process/socket is dead, service ordering), fix it, then re-validate at run 15. No dedicated GitHub issue (user decision). | — |
| 2 | After the API reboot (`system/workflow/restart_domain/request`), sys-usb is restarted but all the vchans are lost (sys-usb and the business domains' too). | Cascade of #262 (the domid write race in `reboot-domain.sh`): the stale domid prevents the Dom0 discovery loop (`create-vchan-tunnels.py`) from recreating the vchan servers with the new domid. Fix #262 (poll the domain state instead of `sleep 3`), then re-validate at run 15. | #262 |

Planned sequence: see [finalization-plan.md](finalization-plan.md) (Phase B: #260, Phase C: #262, Phase D: the tty regression, Phase E: run 15 + #256 closure, Phase F: the hardening second pass #259/#261).

## Run 17 resolutions

Run 17 validated the event flow of the #253/#270 redesign (the `safecor_direct_mount` component reached `ready` on the bus once the channels were up, the business DomUs' `/media/usb` sshfs mounts proactively at the end of boot, the run-16 mdev regression is gone) and exposed two independent blockers that prevented the SFTP I/O from working.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | After the #270 fix, the channels still never started at boot: the controller (non-root since the #253 refactor) had no access to xenstore at all (`EACCES` on `/dev/xen/xenbus`, root-only by default) — the domids were never readable regardless of timing. The manual `chmod 666 /dev/xen/xenbus` (transient) brought the channels and the component up. | The controller initd grants the `safecor` group read access at boot (`chgrp safecor` + `chmod 640`, fallback `660` on a read-only test as the controller user; world access excluded per design rule #10). Re-validated at run 18 on a clean reboot with no manual permission change. | #271 |
| 2 | With the channels up (manual workaround), every SFTP session died at birth and the business DomUs' `/media/usb` sshfs hung on any I/O: the full bwrap command yields a 781-char EXEC address, above socat's 512-byte address-parameter limit (`char token[512]` in xioopen.c; the address is rejected at parse time, the per-domain log shows one truncated `E address "EXEC:"bwrap …` line per session). | A per-domain wrapper script in `/usr/lib/safecor/tmp/sandbox-<domain>` (written by the root channels helper at channel start, removed at stop, 0755) keeps the socat address ≈50 bytes; `bwrap` is resolved to an absolute path at start. Re-validated at run 18. | #272 |
| 3 | The run-17 §2 one-shot probe reported a false negative ("NOT FOUND (timeout)") although the bus log shows the component `ready`: the probe never subscribes to `system/discover/components/response`, and paho-mqtt only delivers on subscribed topics. | The run-18 §3 probe subscribes to the response topic before issuing the request (a test-script fix in the run sheet, no product code change). | — |

## Run 19 resolutions

Run 19 validated #273 (the run-18 `my_config` race is gone: the channels start on their own, the component `ready`, the per-domain logs clean) and #272 (first hardware pass: the wrappers keep the socat address short, the 799-char bwrap command line in the file). Sections 1–4 are green, including the objective (the file I/O through the mount, including the watchdog remount). The run stopped at section 5 (the OFF path): after the `sys-usb` self-restart, `safecor_direct_mount` never reached `ready` again and the business DomUs never remounted.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | After the **non-forced** `restart_domain('sys-usb')` (a self-restart — the controller reboots sys-usb itself via `doas /sbin/reboot`), the domain is destroyed and recreated (domid 1 → 5) but the Dom0 domid cache `/local/domain/system/domids/sys-usb` keeps the old value: a DomU cannot update it (only the forced, Dom0 path — `reboot-domain.sh` — writes it). The Dom0 discovery loop (`create-vchan-tunnels.py`) trusts the stale cache: the three sys-usb vchan servers (msg/input/tty) stay pinned to the old domid, no MQTT comes up from sys-usb, the component never reaches `ready` again, and the business DomUs never remount. The business-domain SFTP side has the same exposure: the client reads the same cache at remount, and the server on sys-usb is pinned to the business domid and only (re)started at sys-usb's boot. | A single self-healing fix, **order-independent** (the Saphir case: `sys-usb` + the two AV domains rebooting simultaneously, order not controlled): (1) the Dom0 loop resolves the **live** domid from the Xen tree `/local/domain/<N>/name` and writes it back to the cache only on difference (≤1 s; the cache is demoted to a self-healed convenience cache — ADR 0006); (2) a SFTP channel supervisor on sys-usb re-conciles each direct-mount channel (start a missing one, re-pin on domid change or server death, reusing the idempotent doas helper + liveness check); (3) the `restart_domain` non-forced branch always publishes a response (honest `refused` + reason for a non-self-restartable business domain) and the `forced` field is added to the API/request (default `false`); (4) `reboot-domain.sh get_domid` → `xl domid` (hardening). Hardware re-validation: [run 20](run-20.md). | #275 |

