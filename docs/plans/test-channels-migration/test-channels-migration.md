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

The runs are described in their own file in the same directory as this file.

## Run 14 resolutions

Run 14 validated #258 (the DomU local MQTT broker) and #264 (the `/etc` permissions on the DomUs, with the run-12 cascades: the GUI input and the API reboot), and exposed two findings.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | The debug tty does not work anymore (regression — it worked at run 13): all the components are present (Dom0: the `vchan-socket-proxy` server, `create-tty-tunnel.sh`, `create-tty-terminal.sh`, `getty` on `/var/run/safecor/tty-admin`; sys-usb: the `tty` vchan client and `socat /dev/ttyUSB0`), so the break is in the chain assembly, probably related to the run-13→14 changes (mosquitto/socat apk dependencies, `safecor-domu-base` made a dependency of `safecor-sys-usb`, the duplicated `setup-vchan` removed from `safecor-sys-usb`). | Diagnose the chain on real hardware (which process/socket is dead, service ordering), fix it, then re-validate at run 15. No dedicated GitHub issue (user decision). | — |
| 2 | After the API reboot (`system/workflow/restart_domain/request`), sys-usb is restarted but all the vchans are lost (sys-usb and the business domains' too). | Cascade of #262 (the domid write race in `reboot-domain.sh`): the stale domid prevents the Dom0 discovery loop (`create-vchan-tunnels.py`) from recreating the vchan servers with the new domid. Fix #262 (poll the domain state instead of `sleep 3`), then re-validate at run 15. | #262 |

Planned sequence: see [finalization-plan.md](finalization-plan.md) (Phase B: #260, Phase C: #262, Phase D: the tty regression, Phase E: run 15 + #256 closure, Phase F: the hardening second pass #259/#261).

