# Run 7

Preparation:
- [x] Rebuild `safecor-core` (mosquitto.conf) and `safecor-lib` (paho socketpair fix) packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode

Verification:
- [x] Verify mosquitto starts on Dom0 (no config error in syslog) -> OK
- [x] Verify the mosquitto listeners exist on Dom0: `/tmp/mqtt-dom0.sock`, `/tmp/mqtt-local.sock`, `/tmp/mqtt-sys-usb.sock`, and one per business domain -> OK
- [x] Verify `/var/log/safecor/vchan-sftp.log` has no more paho traceback (the topology query succeeds) -> The topology query failed 5 on 15 times and stopped logging, maybe it suceeded?
- [x] **Locate the vchan ring data** — on Dom0 run `xenstore-ls /local/domain/system/vchan`, `xenstore-ls /local/domain/0/data/vchan` and, for each DomU, `xenstore-ls /local/domain/<domid>/data/vchan`: the ring data must be found exactly once, and the client/server paths (`setup-vchan.sh`, `create-vchan-tunnels.py`, SFTP client scripts) must be aligned with where `vchan-socket-proxy` actually publishes it -> Xenstore entries are not found.
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb and in the business domains -> It exists in sys-usb but the business domains remain unresponsive (maybe the problem is in safecor-domu-base?)
- [x] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections -> No connection showed. In sys-usb when I stop the service `safecor-sys-usb-controller` and in python I do 
``` 
from safecor import MqttFactory,MqttClient
client=MqttFactory.create_mqtt_client_domu("test")
client.start()
```
The command is stucked and nothing happens.
- [x] Verify MQTT communication between sys-usb and Dom0 (ping) -> Not working
- [x] Verify the boot is not blocked in every domain (sys-usb, business domains, sys-gui): `setup-vchan` and `safecor-vchan-sftp` return immediately and the domains fully boot -> Business domains are stucked at starting.
- [x] Verify the debugging tty on sys-usb -> Not working
- [x] Validate the file read on a USB storage from a Domain (direct mount) -> No access to business domain
- [x] Validate the GUI display -> Not working

- On Dom0, `ps ax | grep vchan` shows the 6 `vchan-socket-proxy` servers as `[vchan-socket-pr]`
  (no command line): they are **zombies** — the servers crashed at startup and
  `create-vchan-tunnels.py` never reaps them (`Popen` without `wait()`), and never
  restarts them (a dead Popen stays in `active_servers` forever).
- Their `stderr` was redirected to `DEVNULL`, so the failure was invisible.

## Root cause (Run 7)

`vchan-socket-proxy -m server` (Dom0 side) calls `libxenvchan_server_init()`, which
opens **`/dev/xen/gntalloc`** (grant allocator — the server allocates the shared ring
page from it) and **`/dev/xen/evtchn`** (event channels) before writing
`ring-ref`/`event-channel` to xenstore. The `create-vchan-tunnels`
service runs as `svc-vchan-tunnels` (non-root) and those device nodes were not
accessible to that user, so every server died with `EACCES` right after startup:

```
$ su -s /bin/sh svc-vchan-tunnels -c "vchan-socket-proxy -v -m server 1 \
    /local/domain/system/vchan/sys-usb/msg /tmp/mqtt-sys-usb.sock; echo rc=\$?"
libxenvchan_server_init: Permission denied
rc=1
```

Consequences (all observed in Run 7):
- no vchan ring data anywhere in xenstore (the servers died before publishing it),
- the DomU clients create their local socket, then block in `connect_vchan()`
  (`xs_watch` on a path that never appears) — this also explains the stuck
  `MqttFactory.create_mqtt_client_domu(...).start()` manual test,
- no MQTT, no SFTP, no tty, business domains stuck at boot.

Note: the vchan channel is created by the **server** side (`libxenvchan_server_init`
writes `ring-ref`/`event-channel` at the given xenstore path, granting read to the
peer domain); the client side only reads them. This is why the ring data was seen in
the DomU's own namespace in Run 3 (the DomU was the server back then, running as
root) and nowhere in Runs 4-7 (the Dom0 server, running unprivileged, crashed).

## Quick fix applied

- [x] `create-vchan-tunnels.initd`: load `xen_gntdev`/`xen_evtchn` and grant the
      `safecor` group (which contains `svc-vchan-tunnels`) read/write access to
      `/dev/gntdev` and `/dev/evtchn` before starting the service; `stop()` also
      kills the orphaned proxy servers.
- [x] `create-vchan-tunnels.py`: the servers' standard error is appended to
      `/var/log/safecor/vchan-servers.log` (instead of `DEVNULL`); `main()` reaps
      exited servers each iteration (`reap_dead_servers`) and restarts them, so a
      failed init is logged and retried instead of being silent and permanent.
- [x] `safecor-core.post-install`: `addgroup svc-vchan-tunnels mosquitto` (the msg
      servers must connect to the Mosquitto UNIX listeners); `create-vchan-tunnels.initd`
      also applies `chmod g+w /tmp/mqtt-*.sock` at service start.
