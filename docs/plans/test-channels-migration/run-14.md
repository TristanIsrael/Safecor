# Run 14

Purpose: validate the #258 fix (the DomU local MQTT broker bridged upstream over the `msg` vchan channel, now started with `mosquitto`/`socat` installed as apk dependencies of `safecor-domu-base`) and the #264 fix (the `/etc` permissions on the DomUs), including the run-12 cascades (findings 2 and 4).

Preparation:
- [ ] Rebuild the `safecor-core`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2` (the #258/#264 fix commits)
- [ ] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [ ] Full cold boot in debug mode (the DomUs are reprovisioned: the apkovl world no longer lists mosquitto/socat, they come from the package dependencies)

Verification — #258, the local broker in a DomU:
- [ ] On a business DomU: `apk info -v mosquitto socat` — both installed (as dependencies of `safecor-domu-base`, not from the world)
- [ ] The `setup-vchan` service is up and the chain is running: the local broker (user `mosquitto`), socat listening on `127.0.0.1:18860`, one `vchan-socket-proxy -m client` for the msg channel
- [ ] The broker config is generated in `/usr/lib/safecor/etc/mosquitto.conf` (the UNIX listener and the `connection safecor-<domain>-bridge` block pointing at `127.0.0.1:18860`)
- [ ] syslog: `Local MQTT broker started (sock=/var/run/safecor/mqtt.sock, bridge=127.0.0.1:18860)`
- [ ] Multiple concurrent MQTT clients in the same DomU (the run-12 failure case): two `mosquitto_pub` on `run14/hello` are both received by a `mosquitto_sub` on the same socket, and all clients stay connected
- [ ] End-to-end over the vchan: publish from the DomU (`run14/e2e`), the message appears in the Dom0 debug log `/var/log/safecor/messages.log`; the opposite direction (publish on Dom0 on `/tmp/mqtt-local.sock`, receive on the DomU local socket) works
- [ ] On Dom0: exactly one upstream connection per domain with the client ID `safecor-<domain>-bridge`

Verification — #264, the sys-usb controller:
- [ ] On a DomU: `stat -c %a /etc` returns `755`
- [ ] The sys-usb controller starts (the libpython EACCES is gone)
- [ ] The GUI input (mouse/touch) works (run-12 finding 2)
- [ ] The API reboot (`system/workflow/restart_domain/request`) works (run-12 finding 4)

Verification — regressions (unchanged channels):
- [ ] On sys-usb, the `input` and `tty` vchan clients are started and their sockets exist (`/var/run/safecor/input.sock`, `/var/run/safecor/tty.sock`)
- [ ] The debug tty works in debug mode
- [ ] The GUI domain displays and the Saphir app starts (its messages are visible on the bus)

Known issues (not fixed yet):
- [ ] #262: `reboot-domain.sh` domid write race
- [ ] #260: the SFTP direct mount does not work
