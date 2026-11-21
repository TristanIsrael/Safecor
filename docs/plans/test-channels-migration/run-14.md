# Run 14

Purpose: validate the #258 fix (the DomU local MQTT broker bridged upstream over the `msg` vchan channel, now started with `mosquitto`/`socat` installed as apk dependencies of `safecor-domu-base`) and the #264 fix (the `/etc` permissions on the DomUs), including the run-12 cascades (findings 2 and 4).

Preparation:
- [x] Rebuild the `safecor-core`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2` (the #258/#264 fix commits)
- [x] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [x] Full cold boot in debug mode (the DomUs are reprovisioned: the apkovl world no longer lists mosquitto/socat, they come from the package dependencies)

Verification — #258, the local broker in a DomU:
- [x] On a business DomU: `apk info -v mosquitto socat` — both installed (as dependencies of `safecor-domu-base`, not from the world)
  - OK
- [x] The `setup-vchan` service is up and the chain is running: the local broker (user `mosquitto`), socat listening on `127.0.0.1:18860`, one `vchan-socket-proxy -m client` for the msg channel
  - OK
- [x] The broker config is generated in `/usr/lib/safecor/etc/mosquitto.conf` (the UNIX listener and the `connection safecor-<domain>-bridge` block pointing at `127.0.0.1:18860`)
  - OK
- [x] syslog: `Local MQTT broker started (sock=/var/run/safecor/mqtt.sock, bridge=127.0.0.1:18860)`
  - OK
- [x] Multiple concurrent MQTT clients in the same DomU (the run-12 failure case): two `mosquitto_pub` on `run14/hello` are both received by a `mosquitto_sub` on the same socket, and all clients stay connected
  - OK
- [x] End-to-end over the vchan: publish from the DomU (`run14/e2e`), the message appears in the Dom0 debug log `/var/log/safecor/messages.log`; the opposite direction (publish on Dom0 on `/tmp/mqtt-local.sock`, receive on the DomU local socket) works
  - OK
- [x] On Dom0: exactly one upstream connection per domain with the client ID `safecor-<domain>-bridge`
  - OK

Verification — #264, the sys-usb controller:
- [x] On a DomU: `stat -c %a /etc` returns `755`
  - OK
- [x] The sys-usb controller starts (the libpython EACCES is gone)
  - OK
- [x] The GUI input (mouse/touch) works (run-12 finding 2)
  - OK
- [x] The API reboot (`system/workflow/restart_domain/request`) works (run-12 finding 4)
  - OK. sysusb is restarted but all the vchans are lost (`sys-usb` and the business domains' too) - probably related to #262 issue not fixed

Verification — regressions (unchanged channels):
- [x] On sys-usb, the `input` and `tty` vchan clients are started and their sockets exist (`/var/run/safecor/input.sock`, `/var/run/safecor/tty.sock`)
  - OK
- [x] The debug tty works in debug mode 
  - KO (this is a regression)
  - In `Dom0`, `vchan-socket-proxy -m server 1 /local/domain/system/vchan/sys-usb/tty /var/run/safecor/sys-usb-tty.sock`, `{create-tty-tunn} /bin/sh /usr/lib/safecor/bin/create-tty-tunnel.sh`, `{create-tty-term} /bin/sh /usr/lib/safecor/bin/create-tty-terminal.sh` and `/sbin/getty -L 115200 /var/run/safecor/tty-admin vt100` are present
  - In `sys-usb`, `socat /dev/ttyUSB0 ...` and the `vchan` are present
- [x] The GUI domain displays and the Saphir app starts (its messages are visible on the bus)
  - OK

## Run 14 resolutions

Run 14 validated #258 and #264 and exposed two findings (the debug tty regression and the vchan loss after an API reboot, a cascade of #262); the SFTP direct mount (#260) remains not working.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | After the API reboot (`system/workflow/restart_domain/request`), sys-usb is restarted but all the vchans are lost (sys-usb's and the business domains' too): `reboot-domain.sh` writes the domid after a `sleep 3`, while the domain is still down (it is destroyed and recreated on reboot), so the stale domid is kept in xenstore and the Dom0 discovery loop (`create-vchan-tunnels.py`, which recreates the vchan servers on domid change) never sees the new domid. | Fix implemented on `version-2`: `reboot-domain.sh` records the old domid, polls for the domain to go down (~30 s), then for it to come back with a new domid (~60 s), and only then writes the new domid to xenstore (exit 1 and no write if it never does, so the controller refuses the restart). To validate on run 15. | #262 |
| 2 | The SFTP direct mount does not work: the sftp-server chroot was never built (the DomU root is a tmpfs), the vchan server was started before the socat UNIX listener it connects to, and the `ro`/`rw` mode of the domain was ignored. | Fix implemented on `version-2`: `safecor-vchan-sftp.py` builds the sftp-server chroot under `/media/usb` at boot (sftp-server + the ldd libraries + the dynamic linker, only when a domain has `direct_mount`), starts the socat UNIX listener before the vchan-socket-proxy server, and passes the domain mode to sftp-server (`-u 077` always, `-R` for `ro` domains); the `DirectMountManager` adds the `reconnect` sshfs option. To validate on run 15. | #260 |
| 3 | The debug tty does not work anymore (regression — it worked at run 13) while all the components are present (Dom0: the `vchan-socket-proxy` server for the tty channel, `create-tty-tunnel.sh`, `create-tty-terminal.sh`, `getty` on `/var/run/safecor/tty-admin`; sys-usb: the `tty` vchan client and `socat /dev/ttyUSB0`): the break is in the chain assembly, probably related to the run-13→14 changes (mosquitto/socat apk dependencies, `safecor-domu-base` made a dependency of `safecor-sys-usb`, the duplicated `setup-vchan` removed from `safecor-sys-usb`). | To diagnose on real hardware at run 15: identify which process/socket of the chain is dead (service states and ordering), fix it, then re-validate the tty. No dedicated GitHub issue (user decision). | — |
