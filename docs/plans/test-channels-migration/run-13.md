# Run 13

Purpose: validate #258 (the DomU local MQTT broker bridged upstream over the `msg` vchan channel) and re-verify the run-12 findings 2 (GUI input) and 4 (API reboot), which are cascades of finding 1 (libpython EACCES, #264).

Preparation:
- [ ] Rebuild the `safecor-core`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2` (commit `820bbda`)
- [ ] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [ ] Full cold boot in debug mode (the DomUs are reprovisioned: the new apkovl has `mosquitto`/`socat` in the world and the local Alpine repository now serves them)

Verification — #258, the local broker in a DomU:
- [ ] On a business DomU, verify the `setup-vchan` service is up and the chain is running:
  - `ps aux | grep -E "mosquitto|socat|vchan-socket-proxy"` — expect the local broker (user `mosquitto`), socat listening on `127.0.0.1:18860`, and one `vchan-socket-proxy -m client` for the msg channel
  - `ip addr show lo` — the loopback interface is up
  - `ls -la /var/run/safecor/mqtt.sock` — the broker socket exists (group `safecor`, mode 660)
  - `cat /var/run/safecor/mosquitto.conf` — the generated config: the UNIX listener and the `connection safecor-<domain>-bridge` block pointing at `127.0.0.1:18860`
  - syslog: `Local MQTT broker started (sock=/var/run/safecor/mqtt.sock, bridge=127.0.0.1:18860)`
  - `apk info -v mosquitto socat` — the packages come from the local repository
- [ ] Verify multiple concurrent MQTT clients in the same DomU (the run-12 failure case):
  ```
  mosquitto_sub -h unix:///var/run/safecor/mqtt.sock -t run13/# -v &
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/hello -m from-client-1
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/hello -m from-client-2
  ```
  Both publishes are received by the subscriber while all clients stay connected (no blocking, no disconnect). If the mosquitto CLI tools are not usable, run two `MqttClient` instances in Python (see `python/emulator/tests/test_domu_mqtt_broker.py` for the pattern).
- [ ] Verify the end-to-end path over the vchan (debug mode): publish from the DomU and check that the message appears in the Dom0 broker debug log `/var/log/safecor/messages.log`:
  ```
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/e2e -m domu-to-dom0
  ```
  Then in the opposite direction: publish on Dom0 (e.g. `mosquitto_pub -h unix:///tmp/mqtt-local.sock -t run13/e2e -m dom0-to-domu`) and receive it with a subscriber on the DomU local socket.
- [ ] On Dom0, verify that exactly one upstream connection per domain is connected to the broker with the client ID `safecor-<domain>-bridge` (the broker log in syslog) and that the `msg` vchan server is attached (syslog + `xenstore-ls /local/domain/system/vchan`).

Verification — regressions (unchanged channels):
- [ ] On sys-usb, the `input` and `tty` vchan clients are started and their sockets exist (`/var/run/safecor/input.sock`, `/var/run/safecor/tty.sock`)
- [ ] The debug tty works in debug mode
- [ ] The GUI domain displays and the Saphir app starts (its messages are visible on the bus)

Verification — run-12 findings re-check:
- [ ] Does the sys-usb controller start? (finding 1: libpython EACCES — #264, expected to still fail unless it is fixed)
  - If it starts:
    - [ ] The GUI input (mouse/touch) works (finding 2)
    - [ ] The API reboot (`system/workflow/restart_domain/request`) works (finding 4)
- [ ] (Known #262, not fixed yet) `reboot-domain.sh sys-usb`: expect `Failed to get domid for sys-usb after reboot`
- [ ] (Known #260, not fixed yet) The SFTP direct mount still does not work

Notes:
- The run-12 findings 2 and 4 can only be validated if finding 1 (the sys-usb controller) starts; they are cascades of the libpython EACCES error tracked in #264.
- The `mosquitto` package of Alpine provides the broker and the CLI tools (`mosquitto_pub`/`mosquitto_sub`); the local broker runs with `allow_anonymous true` in this run (authentication is #259).
- The TCP 1883 listener of the Dom0 broker is still static in this run (the debug-mode-only behavior is #259).
