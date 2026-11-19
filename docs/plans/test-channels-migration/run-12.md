# Run 12

Preparation:
- [x] Rebuild the `safecor-core`, `safecor-lib`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2`
- [x] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [x] In the Saphir repository: add `pango cairo gdk-pixbuf2.0` to the depends of the `saphir` package and rebuild
- [x] Full cold boot in debug mode

Verification:
- [x] Verify all Domains (sys-usb, business, saphir-gui) boot without hanging
  - sys-usb is started but the controller is not started. The initd is crashed.
  - I suspect a permission issue: if I start it manually with the command `su -s /bin/sh svc-sys-usb-controller -c "python3 /usr/lib/safecor/bin/safecor-sys-usb-controller.py"` I get the error: 
```
Error loading shared library libpython3.14.so.1.0: Permission denied (needed by /usr/bin/python3)
Error relocating /usr/bin/python3: Py_BytesMain: symbol not found
```
- [x] Verify the GUI display and the Saphir app start (report generation enabled)
  - The GUI app starts in fullscreen but there is no input (mouse or touch)
  - I can see its messages on the bus
- [x] Verify the GUI domain console: `xl console <gui domain>` shows a login prompt on ttyS0 -> OK
- [x] In saphir-gui, verify the packages mount and the apkovl flow: `cat /etc/fstab`, `mount | grep packages`, `cat /proc/cmdline`, `cat /etc/hostname` — to reconcile with the repository template fstab (`/dev/xvde`) vs the HVM packages vdev (`sde`) -> In domains all the disks appear as `xvd*` even when they are declared `sd*`
- [x] Verify the debug tty after an `xl reboot sys-usb` (the representative API path, not destroy/create)
  - The reboot with the message `system/workflow/restart_domain/request` does not work
  - I rebooter on Dom0 with the script `/usr/lib/safecor/bin/reboot-domain.sh sys-usb` and the domain rebooted but the message `Safecor/reboot-domain.sh: Failed to get domid for sys-usb after reboot`. The message appeared before `sys-usb` had finish turning off.
- [x] Verify the file read on a USB storage from a Domain (direct mount), including a start without USB storage connected — a manual start of `start-direct-mount.py` now reports the failure reason on stderr
  - Tried from `saphir-av-eset`: no mount. Manual start of `start-direct-mount.py` fails after a timeout and no message is sent on the bus.
```
direct-mount: DirectMountManager: timeout waiting for my_config response
direct-mount: DirectMountManager: this domain does not have direct_mount enabled
```
  - The antivirus controller on `saphir-av-eset` answers to the request `system/discover/components/request` so the vchan is ok.
  - See the analysis in the discussion below.

Discussion:
- How the concurrency is managed on the vchan in a Domain? For example if a controller is already started it "takes" the socket, and what happens if another process wants to connect to it after, like the `direct-mount`?
  - Answer: there is a race condition on the socket. If I stop the `av-controller` and I start the `direct-mount` I can see the request on the bus: `system/topology/my_config/request`.
- The SFTP vchan is not working:
  - When I start `direct-mount` I receive no error, the message says that the `Direct mount is ready at /media/usb`, but it is not. When I call `df` it remains stucked.
  - When I check the values of the xenstore at `/local/domain/system/vchan` from inside the `saphir-av-eset` I can see that there is no vchan for sftp.
  - In `sys-usb` I believe the socat command that creates the socket is started after the `vchan-socket-proxy`, but `vchan-socket-proxy` needs to connect to the socket created by socat. So it is reversed in `safecor-vchan-sftp.py` in the package `safecor-sys-usb`.
  - Additionally there might be a problem of permission on the xenstore path, but I am not 100% sure. The xenstore path must be accessible `write` and `read`. -> I modifed the permissions in `set-xenstore-permissions.sh`.
  - When I start the `socat` command then the `vchan-socket-proxy` command I get a repeating error related to the unavailability of `sftp-server`, maybe because it is not in the `chroot` and the binary and its dependencies are not available in the `chroot`
  - In `saphir-av-eset` the command `xenstore-ls /local/domain/system/vchan` returns a permission error (see xenstore permission problem above)
  - The `/media` path is the `chroot` for `sftp-server` so it should contain:
    - The `musl` library in `/media/lib`, 
    - The binary `/media/bin/sftp-server`,
    - The special device `/media/dev/null`,
    - The file `/media/etc/passwd` with `root:x:0:0:root:/root:/sbin/nologin`,
    - The binary `/sbin/nologin`
  - After all these steps the sftp tunnel works
- Security concerns about the SFTP server:
  - The sftp server starts in the chroot `/media` and it exposes all the `/media` directory. The client would expect the root to be the `/media/usb` directory because the file paths are constructed with this root and the disk name, for example `/my_disk` will be mounted under `/media/usb/my_disk` on `sys-usb`.
  - It seems that there is no way to force the sftp server to start in the subdirectory `usb` so the chroot should probably be `/media/usb`
  - It might be useful to add the `-P` filter for denied SFTP requests or `-p` for the allowed SFTP requests.
  - Also we might use the `-u` option for the umask of the created files.
  - For the read-only channels we should also add the `-R` option.

Resolution: the analysis of the seven findings and their resolutions are recorded in [test-channels-migration.md](test-channels-migration.md) (section "Run 12 resolutions"). The follow-up issues are #258 to #264.
  

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
| #258 | DomU local MQTT broker with an upstream vchan bridge | In progress (run-13 failure, fix committed, run 14 pending) |
| #259 | Enforce MQTT client ID naming convention and broker authentication | Ready |
| #260 | Fix the SFTP vchan channel startup order and package the sftp-server chroot | Ready |
| #261 | Restrict xenstore write grants to the vchan subtree | Ready |
| #262 | Fix the domid write race in reboot-domain.sh | Ready |
| #263 | Update the project documentation and the Safecor Wiki for the v2 MQTT/vchan architecture (includes the Mermaid HLD/LLD step) | In progress (diagrams done, full sync after #259) |
| #264 | Investigate the libpython EACCES error on the sys-usb domain | In review (root cause: /etc 0700, fix committed, run 14 pending) |

Planned sequence: commit the run-12 working-tree fixes under #256 -> #258 -> run 13 (re-verify findings 2 and 4) -> #259 -> #260, #261, #262 -> #263 -> #264 when time is available.