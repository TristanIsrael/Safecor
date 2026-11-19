# Validation tests for the migration from channels to pvchan

## Objectives

The objectives are:

[ ] Validate the channels replacement for the messaging on all Domains
[ ] Validate the channels replacement for the inputs on sys-usb
[ ] Validate the channels replacement for the debugging tty on sys-usb
[ ] Validate the file read on a USB storage from a Domain
[ ] Validate the GUI display

## Runs

The runs are described in their own file in the same directory as this file.

## Run 12 resolutions

Run 12 exposed seven findings. Their resolutions are recorded here for tracking.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | The sys-usb controller cannot load `libpython3.14.so.1.0` (EACCES). The lost-`.so`-exec-bits theory was refuted: the same boot ISO serves every domain and other python processes work on sys-usb. | Investigation deferred. Open question: which user run the working python processes (root bypasses the exec check, so the theory is not fully excluded). | #264 (Not ready) |
| 2 | The GUI has no input (cascade of 1: `InputsDaemon` runs inside the sys-usb controller process). | Re-verified on run 13 after 1 is fixed. | — |
| 3 | The HVM config disk is invisible/wrong in the guest (HVM guests see every disk as `xvd*` regardless of the declared vdev; `devtype=cdrom` on a raw ext4 image makes the guest see a CD-ROM). | Fixed: removed `devtype=cdrom` from the HVM `sdd` disk in `create-domains.py` (committed under #256, sha512 recalculated). | #256 |
| 4 | The API reboot (`system/workflow/restart_domain/request`) does not work (cascade of 1: the controller is dead). Known gaps once 1 is fixed: the self-reboot never updates `/local/domain/system/domids/<name>`, and the non-forced path publishes no response. | Re-verified on run 13; the domid-write race is tracked separately. | #262 |
| 5 | `reboot-domain.sh` writes a stale domid (`sleep 3` is too short). | Fix: poll for the domain to disappear (~30 s), then poll until Running with a valid ID (~60 s), then write the domid. | #262 |
| 6 | Only one MQTT client per domain works on the `msg` vchan (the Dom0 server is single-connection; a second client blocks). | Accepted architecture: a local mosquitto broker per DomU + a single upstream bridge over the vchan (validated below). | #258 |
| 7 | The SFTP vchan channel does not work: (a) the proxy is started before socat in `safecor-vchan-sftp.py`, (b) the sftp-server chroot is never built (tmpfs `/media`), (c) the xenstore write grants. | (a)+(b)+security list: fix the order, package the chroot under `/media/usb` with `-R`/`-P`/`-p`/`-u`. (c): the interim `r` → `b` change is committed under #256, the refinement is tracked separately. | #260, #261 |

### The mosquitto bridge over vchan (finding 6)

Verified against the mosquitto man page (2.0.18, the version shipped by Alpine 3.20, and master):

- The bridge outbound connection is **TCP-only** (`address host[:port]`, default 1883). A bridge cannot connect to a UNIX socket.
- The listeners **support UNIX sockets** (`listener 0 <path>`).
- The bridge topic patterns **accept wildcards** (`topic # both 0` is valid).

The vchan hop therefore goes through a TCP loopback endpoint:

```
apps -> /var/run/safecor/mqtt.sock (local broker UNIX listener)
     -> local broker bridge -> 127.0.0.1:<port>
     -> socat TCP-LISTEN:<port>,fork EXEC:"vchan-socket-proxy -m client 0 <msg xspath> -"
     -> vchan -> Dom0 server proxy (create-vchan-tunnels.py, unchanged)
     -> Dom0 broker UNIX listener /tmp/mqtt-<name>.sock
```

Precondition: the DomUs have no loopback interface (see the `_socketpair_compat` workaround in `python/lib/src/safecor/_mqtt_client.py`), so the DomU boot must bring up `lo`.

Side benefit: the local broker multiplexes the local clients, so the single-vchan-connection limit (finding 6) disappears. It also makes the `Api` singleton removable (future study).

### MQTT client IDs and authentication (decision)

- Client ID convention: `safecor-<scope>-<name>` (lowercase, kebab-case, no spaces). Dom0: `safecor-dom0-controller`, `safecor-dom0-orchestrator`, `safecor-dom0-check-system`. DomU: `safecor-<domain>-<component>`. Bridges: `remote_clientid safecor-<domain>-bridge`. The identifier stays a mandatory argument of `MqttFactory.create_mqtt_client_*()`, and the library validates the format.
- No anonymous clients on the product brokers: `allow_anonymous false` + `password_file` (one account per service identity, generated at install/provisioning time). The `MqttClient` reads the credentials from a Safecor config file and calls `username_pw_set`. The emulator/development broker keeps `allow_anonymous true`.
- The Dom0 broker TCP listener 1883 is kept **in debug mode only** (required for the development Mosquitto client) and disabled in non-debug mode: the `debug` openrc service (active only when `DEBUG=ON` is on the kernel cmdline) installs the listener snippet in `/etc/mosquitto/conf.d/` and reloads mosquitto; the static block is removed from the packaged `conf/mosquitto.conf`.
- Tracker: #259.

### Architecture diagrams (step)

Produce a High Level Design (HLD) and a Low Level Design (LLD) of the messaging architecture as **Mermaid** diagrams (domains, brokers, vchan proxies, socat, sockets), embedded in the project documentation (`/docs/architecture.md`) and in the Safecor Wiki. Tracker: #263.

## Follow-up issues

| Issue | Title | Status |
|---|---|---|
| #258 | DomU local MQTT broker with an upstream vchan bridge | In review |
| #259 | Enforce MQTT client ID naming convention and broker authentication | Ready |
| #260 | Fix the SFTP vchan channel startup order and package the sftp-server chroot | Ready |
| #261 | Restrict xenstore write grants to the vchan subtree | Ready |
| #262 | Fix the domid write race in reboot-domain.sh | Ready |
| #263 | Update the project documentation and the Safecor Wiki for the v2 MQTT/vchan architecture (includes the Mermaid HLD/LLD step) | Not ready (depends on #258/#259) |
| #264 | Investigate the libpython EACCES error on the sys-usb domain | Not ready (deferred investigation) |

Planned sequence: commit the run-12 working-tree fixes under #256 -> #258 -> run 13 (re-verify findings 2 and 4) -> #259 -> #260, #261, #262 -> #263 -> #264 when time is available.
