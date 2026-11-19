# Run 13

Purpose: validate #258 (the DomU local MQTT broker bridged upstream over the `msg` vchan channel) and re-verify the run-12 findings 2 (GUI input) and 4 (API reboot), which are cascades of finding 1 (libpython EACCES, #264).

Preparation:
- [x] Rebuild the `safecor-core`, `safecor-domu-base` and `safecor-sys-usb` packages from `version-2` (commit `820bbda`)
- [x] On Dom0: `apk update && apk add safecor-core`, then `apk info -v safecor-core`
- [x] Full cold boot in debug mode (the DomUs are reprovisioned: the new apkovl has `mosquitto`/`socat` in the world and the local Alpine repository now serves them)

Verification — #258, the local broker in a DomU:
- [x] On a business DomU, verify the `setup-vchan` service is up and the chain is running:
   listening on `127.0.0.1:18860`, and one `vchan-socket-proxy -m client` for the msg channel
    - On `saphir-av-clamav` during the boot `safecor-domu-base` complains about `/usr/bin/socat` missing. Indeed `socat` is installed later in the boot process.
    - Consequently the only vchan is `msg` 
    - `mosquitto` is not running. It is declared in `/etc/apk/world` with `socat`. But as socat starts to late, I believe that mosquitto cannot start either. The chain is not correct.
    - In don't like the fact that `mosquitto` and `socat` are managed by the `/etc/apk/world` and injected in the packages, it reduces the links between the packages and the traceability. I prefer using apk dependencies in `safecor-domu-base` for example (but also for `safecor-sys-usb` => maybe `safecor-domu-base` should be a dependancy for `safecor-sys-usb` but with exceptions for different operations that should be done in `safecor-sys-usb`).
  - `ip addr show lo` — the loopback interface is up
  - `ls -la /var/run/safecor/mqtt.sock` — the broker socket exists (group `safecor`, mode 660)
    - OK
  - `cat /var/run/safecor/mosquitto.conf` — the generated config: the UNIX listener and the `connection safecor-<domain>-bridge` block pointing at `127.0.0.1:18860`
    - This is not the right place for this configuration file, it should be in `/usr/lib/safecor/etc`
  - syslog: `Local MQTT broker started (sock=/var/run/safecor/mqtt.sock, bridge=127.0.0.1:18860)`
    - KO
  - `apk info -v mosquitto socat` — the packages come from the local repository  
    - OK   
- [x] Verify multiple concurrent MQTT clients in the same DomU (the run-12 failure case):
  ```
  mosquitto_sub -h unix:///var/run/safecor/mqtt.sock -t run13/# -v &
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/hello -m from-client-1
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/hello -m from-client-2
  ```
  Both publishes are received by the subscriber while all clients stay connected (no blocking, no disconnect). If the mosquitto CLI tools are not usable, run two `MqttClient` instances in Python (see `python/emulator/tests/test_domu_mqtt_broker.py` for the pattern).
    - KO because of the previous errors
- [x] Verify the end-to-end path over the vchan (debug mode): publish from the DomU and check that the message appears in the Dom0 broker debug log `/var/log/safecor/messages.log`:
  ```
  mosquitto_pub -h unix:///var/run/safecor/mqtt.sock -t run13/e2e -m domu-to-dom0
  ```
  Then in the opposite direction: publish on Dom0 (e.g. `mosquitto_pub -h unix:///tmp/mqtt-local.sock -t run13/e2e -m dom0-to-domu`) and receive it with a subscriber on the DomU local socket.
  - Not tested because of the previous errors
- [x] On Dom0, verify that exactly one upstream connection per domain is connected to the broker with the client ID `safecor-<domain>-bridge` (the broker log in syslog) and that the `msg` vchan server is attached (syslog + `xenstore-ls /local/domain/system/vchan`).
  - KO because of the previous errors
Verification — regressions (unchanged channels):
- [x] On sys-usb, the `input` and `tty` vchan clients are started and their sockets exist (`/var/run/safecor/input.sock`, `/var/run/safecor/tty.sock`)
  - `input` vchan is present
  - `tty` vchan is present
- [x] The debug tty works in debug mode
  - OK
- [x] The GUI domain displays and the Saphir app starts (its messages are visible on the bus)
  - KO because of the previous errors

Verification — run-12 findings re-check:
- [x] Does the sys-usb controller start? (finding 1: libpython EACCES — #264, expected to still fail unless it is fixed)  
  - The problem comes from the `/etc` directory that has permission `0700` instead of `0755`.
  - It does not start. The library still cannot be loaded.
  - If it starts:
    - [ ] The GUI input (mouse/touch) works (finding 2)
    - [ ] The API reboot (`system/workflow/restart_domain/request`) works (finding 4)
- [ ] (Known #262, not fixed yet) `reboot-domain.sh sys-usb`: expect `Failed to get domid for sys-usb after reboot`
- [ ] (Known #260, not fixed yet) The SFTP direct mount still does not work

Notes:
- The run-12 findings 2 and 4 can only be validated if finding 1 (the sys-usb controller) starts; they are cascades of the libpython EACCES error tracked in #264.
- The `mosquitto` package of Alpine provides the broker and the CLI tools (`mosquitto_pub`/`mosquitto_sub`); the local broker runs with `allow_anonymous true` in this run (authentication is #259).
- The TCP 1883 listener of the Dom0 broker is still static in this run (the debug-mode-only behavior is #259).

## Run 13 resolutions

Run 13 exposed one blocking finding for #258 and identified the root cause of #264.

| # | Finding | Resolution | Tracker |
|---|---|---|---|
| 1 | The local mosquitto broker is not started in the DomUs (observed on `saphir-av-clamav`): at the time the `safecor-domu-base` post-install ran `setup-vchan.sh`, `mosquitto`/`socat` were not installed yet. They were only present in the apkovl world (no apk dependency), and the post-install runs inside the blocking `apk add` transaction, so the script's 60 s wait can never succeed when apk orders them after `safecor-domu-base` (a race). | Fix: declare `mosquitto` and `socat` as apk dependencies of `safecor-domu-base` (installed before the post-install) and `safecor-domu-base` as a dependency of `safecor-sys-usb` (removes the duplicated `setup-vchan.{sh,initd}`); remove `mosquitto`/`socat` from the apkovl world; the broker config is generated in `/usr/lib/safecor/etc/mosquitto.conf`. To validate on run 14. | #258 |
| 2 | The sys-usb controller still cannot load libpython (run-12 finding 1): the root cause is the `/etc` permission `0700` instead of `0755` on the DomUs — the apkovl tarball packaged by `safecor-core` carries its directory entries with 0700 mode, and the non-root controller user cannot traverse `/etc`. | Fix: regenerate the apkovl tarball with 0755 directory entries + `chmod 0755 /etc` in the apkovl `safecor-core-init` service (self-healing). To validate on run 14 (including the cascades: findings 2 and 4). | #264 |
