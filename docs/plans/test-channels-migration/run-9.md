# Run 9

Preparation:
- [x] Rebuild `safecor-core` package (with the `/dev/xen/*` + `xen_gntalloc` fix)
- [x] Rebuild `safecor-sys-usb` and `safecor-domu-base` packages (with the
      vchan bridge socket permissions fix)
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode

Verification:
- [x] Verify `/dev/xen/gntdev`, `/dev/xen/evtchn`, `/dev/xen/gntalloc` are group
      `safecor`, mode `0660` -> `/dev/xen/gntalloc` is still owned by root:root so it prevents the channels to be created.
- [x] Verify the `vchan-socket-proxy` servers are alive on Dom0 (full command line in
      `ps ax`, no `[vchan-socket-pr]` zombies) -> They are zombies and continuously restarted until the permission is fixed on `/dev/xen/gntalloc`
- [x] Verify `xenstore-ls /local/domain/system/vchan` lists one entry per domain
      (msg for all, input/tty for sys-usb) -> OK
- [x] Verify the DomU vchan clients connect: the Dom0 servers connect to the mosquitto
      sockets (no more zombies in `ps ax`; `/var/log/safecor/vchan-tunnels.log` clean) -> It worked until in Dom0 the vchan server exited for no reason. After that the sys-usb controller lost its connection to the mqtt broker. See logs below. Then I relaunched the sys-usb vchans and controller and the connection stood.
- [x] Verify `/var/run/safecor/*.sock` in sys-usb are group `safecor`, mode `0660`
      (`ls -l /var/run/safecor`) -> OK
- [x] Verify the sys-usb controller (user `svc-sys-usb-controller`, started through
      its initd) sends `discover_components/response` and answers pings -> Not the first time but when relaunched ok
- [x] Verify MQTT communication between sys-usb and Dom0 (ping) -> Ok after resolve the problems
- [x] Verify the boot is not blocked in every domain (sys-usb, business domains, sys-gui) -> All the business domains are blocked
- [x] Verify the debugging tty on sys-usb -> Not working. In `create-tty-tunnel.sh` in `safecor-sys-usb` it seems to be still connecting to `/dev/hvc3`.
- [x] Validate the file read on a USB storage from a Domain (direct mount) -> Impossible
- [x] Validate the GUI display -> No display

Logs:
- `/var/log/messages`
```
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=msg sock=/tmp/mqtt-sys-usb.sock
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=input sock=/var/run/safecor/sys-usb-input.sock
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=tty sock=/var/run/safecor/sys-usb-tty.sock
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=2 channel=msg sock=/tmp/mqtt-saphir-gui.sock
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=3 channel=msg sock=/tmp/mqtt-saphir-av-clamav.sock
2026-11-17 11:20:30 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=4 channel=msg sock=/tmp/mqtt-saphir-av-eset.sock
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=1 channel=msg exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=1 channel=input exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=1 channel=tty exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=2 channel=msg exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=3 channel=msg exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=4 channel=msg exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=msg sock=/tmp/mqtt-sys-usb.sock
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=input sock=/var/run/safecor/sys-usb-input.sock
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=tty sock=/var/run/safecor/sys-usb-tty.sock
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=2 channel=msg sock=/tmp/mqtt-saphir-gui.sock
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=3 channel=msg sock=/tmp/mqtt-saphir-av-clamav.sock
2026-11-17 11:20:31 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=4 channel=msg sock=/tmp/mqtt-saphir-av-eset.sock
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: Client /tmp/mqtt-sys-usb.sock [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: Client /tmp/mqtt-sys-usb.sock [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: Client /tmp/mqtt-sys-usb.sock [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: Client /tmp/mqtt-sys-usb.sock [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: New client connected from /tmp/mqtt-sys-usb.sock:0 as safecor-vchan-sftp (p4, c1, k30).
2026-11-17 11:20:31 notice mosquitto[3584]: 1794914431: Client safecor-vchan-sftp [/tmp/mqtt-sys-usb.sock:0] disconnected: connection closed by client.
2026-11-17 11:20:32 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=1 channel=msg exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:20:32 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=msg sock=/tmp/mqtt-sys-usb.sock
2026-11-17 11:26:24 notice mosquitto[3584]: 1794914784: New connection from /tmp/mqtt-sys-usb.sock:0 on port 0.
2026-11-17 11:26:24 notice mosquitto[3584]: 1794914784: New client connected from /tmp/mqtt-sys-usb.sock:0 as sys-usb (p4, c1, k30).
2026-11-17 11:26:24 err Safecor/create-vchan-tunnels[4103]: vchan server exited: domid=1 channel=input exit_code=1 — see /var/log/safecor/vchan-servers.log — will restart
2026-11-17 11:26:24 info Safecor/create-vchan-tunnels[4103]: vchan server started: domid=1 channel=input sock=/var/run/safecor/sys-usb-input.sock
```
- `/var/log/safecor/vchan-servers.log`
```
-- truncated --
libxenvchan_server_init: Permission denied
libxenvchan_server_init: Permission denied
libxenvchan_server_initlibxenvchan_server_init::  Permission deniedPermission denied

vchan write failed
connect: Permission denied
connect_socket failed
```

## Run 9 analysis

The run confirmed the DomU socket-permission fix (`ls -l /var/run/safecor`
in sys-usb shows group `safecor`, mode `0660`, and the `msg` channel works
end-to-end once `/dev/xen/gntalloc` is fixed manually). Three distinct bugs
remain, all on the Dom0 side or in legacy code:

### Bug C1 — `/dev/xen/*` node permissions not applied at boot

After a fresh boot, `/dev/xen/gntalloc` is still `root:root`, so every vchan
server fails with `libxenvchan_server_init: Permission denied` and loops in
restarts (see logs). While the servers are down, all business domains hang
at boot (their apps wait for MQTT) and the GUI never starts.

Two possible causes, both addressed:

1. **Stale package on Dom0**: rebuilding the packages and refreshing the
   local repository does not update Dom0. If Dom0 still runs an older
   `create-vchan-tunnels` init script (the one that fixed the
   non-existent `/dev/gntdev` path), the observed behavior is exactly this.
   To check on Dom0: `apk info -v safecor-core`.
2. **A real race**: `modprobe` returns before udev has created the nodes
   (asynchronous). The `[ -e ]` test in the init script is then false, the
   `chgrp` is skipped, and the node appears 10 ms later as `root:root`.

Note: the openrc `user=` variable is not a special one (the standard
mechanism is `command_user` + `start-stop-daemon --user`), so the init
script `start()` runs as root: the init script logic itself was sound.

Fix: a udev rule shipped by `safecor-core`
(`/etc/udev/rules.d/99-safecor-xen.rules`) applies `GROUP="safecor"`,
`MODE="0660"` to `gntdev`, `gntalloc` and `evtchn` every time a node is
created — no race. The init script also waits up to 10 s for the nodes and
logs each step.

### Bug C2 — input/tty servers: `connect: Permission denied` on the local Dom0 sockets

Even after the manual gntalloc fix (11:26:24), the `input` vchan server
keeps exiting with `exit_code=1`: `vchan-servers.log` shows
`connect: Permission denied` / `connect_socket failed`. The vchan servers
(user `svc-vchan-tunnels`, group `safecor`) connect to sockets created by
other processes:

- `sys-usb-input.sock` → created by `inputs_proxy.py` (orchestrator,
  `svc-orchestrator`)
- `sys-usb-tty.sock` → created by the `socat` tty tunnel (`svc-tty-tunnels`)

`/var/run/safecor` is a setgid `safecor` directory on Dom0 (the orchestrator
sets it to `2770`), so the group is already correct: only the mode was
wrong (`0755`, no group write bit). Same bug family as the DomU fix, on the
Dom0 side. (The `msg` servers connect to mosquitto listener sockets, which
already work — see the mosquitto log.)

Fix: `chmod 0660` at creation time — in `inputs_proxy.py` after `bind()`,
and in `create-tty-tunnel.sh` (Dom0), which now waits for the socket to
appear and applies `chgrp safecor` + `chmod 660`.

### Bug C3 — DomU debug tty still bridged to the legacy serial console

`create-tty-tunnel.sh` in `safecor-sys-usb` bridged `$DEVNAME` to `/dev/hvc3`
(the old serial console), not the vchan tty channel. Fix: bridge it to the
vchan tty client socket (`/var/run/safecor/tty.sock`) with a wait loop.

### "The server stopped for no reason"

The vchan-socket-proxy server survives client disconnections (its loop
returns to waiting for the next client). An `exit_code=1` corresponds to
either the init (gntalloc — C1) or `connect_socket` (C2). If it happens
again in run 10, `vchan-servers.log` will give the exact error.

### Business domains blocked at boot

Cascading effect of C1: their `msg` channel was down during boot. With C1
fixed, the Dom0 server starts a few seconds after the domid is registered
in xenstore. To validate on the cold boot of run 10 — if a domain still
hangs while its channel is up, its boot logic does not retry (the business
code is not in this repository).
