# Validation tests for the migration from channels to pvchan

## Objectives

The objectives are:

[ ] Validate the channels replacement for the messaging on all Domains
[ ] Validate the channels replacement for the inputs on sys-usb
[ ] Validate the channels replacement for the debugging tty on sys-usb
[ ] Validate the file read on a USB storage from a Domain
[ ] Validate the GUI display

## Run 1

- There is no log for the new services, we should have a dedicated log for each service in `/var/log/safecor`.
- When we run `/usr/bin/python3 /usr/lib/safecor/bin/create-vchan-tunnels.py` there is no output, so we don't know whether the service is starting correctly or not.
- No MQTT communication between `sys-usb` and `Dom0`
  - The system has not been started in debug mode
  - Dom0 diag:
    - The service `create-vchan-tunnels` is started and alive
    - `# xenstore-ls /local/domain/system` returns 
    ```
    screen_size = "800,1280"
    screen_rotation = "90"
    input-focus = "saphir-gui"
    debug_on = "1"
    ```
    - `# xenstore-ls /local/domain/system/domids` returns `xenstore-ls: xs_directory (/local/domain/system/domids): No such file or directory`
    - The file `/var/run/safecor/mqtt.sock` does not exist
    - The command `# xenstore-read /local/domain/<domid>/data/vchan/msg` returns an error for every domain.
    - The file `/var/log/safecor/vchan-tunnels.log` does not exist
    - The file `/var/run/safecor/mqtt-tunnels.log` does not exist
  - DomU diag:
    - During the boot the following log is shown: `Starting vchan SFTP channels ...Safecor/safecor-vchan-sftp: Failed to query topology via MQTT`
    - The command `xenstore-read /local/domain/system/domids/$(hostname)` returns `xenstore-read: couldn't read path /local/domain/system/domids/sys-usb`
    - The binary `vchan-socket-proxy` exists
    - The folder `/var/run/safecor` is empty
    - The process `vchan-socket-proxy` is not alive
    - The command `xenstore-read /local/domain/6/data/vchan/msg` returns `xenstore-read: couldn't read path /local/domain/6/data/vchan/msg`

### Root cause

`start-sys-usb.sh` and `start-business-domain.sh` used `xl info <domain> | grep -w ID | awk '{print $3}'` to retrieve the domid. This is **not a valid Xen command** — `xl info` only works without arguments (it lists all domains). The variable `domid` was always empty, so `xenstore-write` was never executed.

### Fix applied

- Replaced `xl info <name> | grep -w ID | awk '{print $3}'` with `xl domid <name>` in:
  - `start-sys-usb.sh`
  - `start-business-domain.sh` (both GUI and non-GUI paths)
- Added a `print()` at startup in `create-vchan-tunnels.py` for visibility in debug mode logs.
- Logs are available in debug mode (`DEBUG=ON` kernel parameter).

## Run 2

- [x] Rebuild `safecor-core` package
- [x] Boot in debug mode
- [x] Verify `xenstore-read /local/domain/system/domids/sys-usb` returns a numeric domid
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb -> It does not exist
- [x] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0 -> It does not exist
- [x] Verify `/var/log/safecor/vchan-tunnels.log` contains the discovery messages -> Contains `vchan-tunnels: starting discovery loop`
- [x] Verify MQTT communication between sys-usb and Dom0 -> no communication

### Root cause

`/etc/init.d/setup-vchan` does not exist in the sys-usb DomU. The `setup-vchan.sh`
script and `setup-vchan.initd` were only in `safecor-domu-base` (business domains),
but `sys-usb` uses `safecor-sys-usb` which does not depend on `safecor-domu-base`.

### Fix applied

- Added `setup-vchan.sh` and `setup-vchan.initd` to `safecor-sys-usb` package
- Added `rc-update add setup-vchan default` to `safecor-sys-usb` post-install
- Added `rc-update add setup-vchan default` to `safecor-domu-base` post-install

## Run 3

- [x] Rebuild `safecor-sys-usb` and `safecor-domu-base` packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode
- [x] Verify `/etc/init.d/setup-vchan` exists in sys-usb -> OK
- [x] Verify `rc-service setup-vchan status` is -> OK
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb -> No
- [x] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0 -> does not exist
- [x] Verify MQTT communication between sys-usb and Dom0 -> not working

- When booting, `sys-usb` wait a long time before showing the error `Safecor/safecor-vchan-sftp: Failed to query topology via MQTT`. It should fail sooner. Same thing for the start of the vchan SFTP channels.
- `safecor-sys-usb-controller` starts before the vchan.
- In `sys-usb` the vchans seem to be configured: 
```
xenstore-ls /local/domain/$MY_DOMID/data/vchan
msg = ""
 ring-ref = "74"
 event-channel = "24"
tty = ""
 ring-ref = "76"
 event-channel = "26"
input = ""
 ring-ref = "75"
 event-channel = "25"
```
- In Dom0 the process `/usr/bin/python3 -u /usr/lib/safecor/bin/create-vchan-tunnels.py` is running but the command `rc-service create-vchan-tunnels status` returns nothing.
- There are no vchan socket in Dom0 in `/var/run/safecor`
- `/var/log/safecor/vchan-tunnels.log` only contains `vchan-tunnels: starting discovery loop`

### Root cause

`vchan_endpoint_exists()` checked if `xenstore-read /local/domain/<N>/data/vchan/msg`
returned a non-empty value. But the vchan path itself has an **empty value** — the data
is in sub-keys (`ring-ref`, `event-channel`). The check always returned `False`, so the
Dom0 never started the vchan client.

### Fix applied

- Changed `vchan_endpoint_exists()` to check the `ring-ref` sub-key instead:
  `xenstore-read /local/domain/<N>/data/vchan/<channel>/ring-ref`
- Added `after setup-vchan` dependency in `safecor-sys-usb-controller.initd` to ensure
  the vchan servers are up before the controller tries to connect to MQTT.

## Run 4

- [x] Rebuild `safecor-core` and `safecor-sys-usb` packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb -> No
- [x] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0 -> Does not exist
- [x] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections -> No
- [x] Verify MQTT communication between sys-usb and Dom0 -> There is no connection in the file


## Run 5

- [x] Rebuild `safecor-core` and `safecor-sys-usb` packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode
- [ ] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb
- [x] Verify the vchan `msg` server connects to the mosquitto listener on Dom0 -> It connects to `/tmp/mqtt_msg_1.sock` (the listener name is wrong: it is named by domid with a typo, not by domain name; `sys-usb-input.sock` and `sys-usb-tty.sock` exist)
- [ ] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections
- [x] Verify MQTT communication between sys-usb and Dom0 -> There is no connection in the file

- Sys-usb is to long to fail on socket connection. It waits 2 or 3 minutes a first time then it is blocked on `Starting vchan SFTP channels`. Maybe the vchan is created but the process is blocking because of a `wait` and should be started detached?
- in `safecor-sys-usb`, the file `safecor-vchan-sftp.initd` should be split into one `initd` file and one shell ou python script with the logic. 
- The Domains don't have access to `/local/domain/0` so the vchan information should not be written in this scope. Instead, write them into `/local/domain/system/vchan/<domain name>/<channel>` which is already shared with all the domains. 

### Root cause

Three issues combined prevented the vchan clients from connecting:

1. **Wrong vchan namespace.** The vchan servers/clients used the xenstore path
   `/local/domain/0/data/vchan/<domid>/<channel>`, but a DomU cannot read
   `/local/domain/0` — the `ring-ref` was never visible from the DomU side, so
   the clients could not connect. The data must live in the shared namespace
   `/local/domain/system/vchan/<domain name>/<channel>` (readable by all DomUs,
   see `set-xenstore-permissions.sh`).
2. **Missing / misnamed mosquitto listener.** The DomU vchan server for the `msg`
   channel connects to the mosquitto UNIX listener `/tmp/mqtt_msg_<domid>.sock`, but
   no such listener was created, and the name was based on the domid, which is not
   stable across reboots.
3. **Blocking boot.** `setup-vchan.sh` waited on the vchan clients (blocking the
   boot for minutes) and `safecor-vchan-sftp.initd` contained the whole logic in the
   initd script.

### Actions

- [x] **A — `safecor-core`**: `create-vchan-tunnels.py` uses the shared namespace
      `/local/domain/system/vchan/<domain name>/<channel>` for the vchan data and the
      name-based mosquitto socket `/tmp/mqtt-<domain name>.sock` (a single, throttled
      error log if the listener is missing).
- [x] **A — `safecor-core`**: new `generate-mosquitto-listeners.py` writes
      `/etc/mosquitto/conf.d/safecor-listeners.conf` (one `listener 0 /tmp/mqtt-<domain>.sock`
      per DomU of the topology) at the end of the product installation
      (`finish-core-init.sh`); `mosquitto.conf` includes it and defines the static
      `/tmp/mqtt-local.sock` and `/tmp/mqtt-dom0.sock` listeners.
- [x] **B — `safecor-sys-usb`**: `setup-vchan.sh` starts the vchan clients (msg, input, tty)
      detached (`start-stop-daemon`, one pidfile per channel) against the shared namespace,
      with a 15 s wait for the Dom0 vchan data instead of blocking the boot.
- [x] **B — `safecor-sys-usb`**: `safecor-vchan-sftp` split into a thin `initd` +
      `safecor-vchan-sftp.py`, started detached, retrying the topology query (15 × 10 s)
      until MQTT is available; the SFTP channel uses the shared namespace and resolves the
      peer domid at runtime.
- [x] **C — `safecor-domu-base`**: same `setup-vchan.sh` / `setup-vchan.initd` as sys-usb;
      `setup-direct-mount.sh` generates the vchan SFTP client with the runtime domid and the
      shared namespace path.
- [x] **D — `safecor-lib`**: `Constants.MQTT_MSG_BROKER_SOCKET` → `/tmp/mqtt-dom0.sock`,
      `MQTT_MSG_BROKER_SOCKETS` → `/tmp/mqtt-*.sock`; `DirectMountManager.__generate_vchan_script`
      generates the client script with the runtime domid and the shared namespace path.
- [x] **E — docs**: `docs/architecture.md` (§2.3, §3.1 transports, xenstore key model) updated
      with the new sockets and the `vchan/<name>/<channel>` namespace.

## Run 6

Preparation:
- [x] Rebuild `safecor-core`, `safecor-sys-usb` and `safecor-domu-base` packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode

Verification:
- [x] Verify `xenstore-ls /local/domain/system/vchan` lists one entry per domain (msg for all, input/tty for sys-usb) -> `xenstore-ls /local/domain/system/vchan` returns `xenstore-ls: xs_directory (/local/domain/system/vchan): No such file or directory`
- [x] Verify where `vchan-socket-proxy` (server side) actually writes the ring data — if it does not land in the shared namespace, adjust the 15 s wait / path in `setup-vchan.sh` -> See the previous point
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb and in the business domains -> It exists in sys-usb.
- [x] Verify the mosquitto listeners exist on Dom0: `/tmp/mqtt-dom0.sock`, `/tmp/mqtt-local.sock`, `/tmp/mqtt-sys-usb.sock`, and one per business domain -> OK
- [x] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections -> No connection showed. See the connection problem below.
- [x] Verify MQTT communication between sys-usb and Dom0 -> not working
- [x] Verify the boot is not blocked: `setup-vchan` and `safecor-vchan-sftp` return immediately and the clients keep running detached -> OK in `sys-usb` but not the others business domains including `sys-gui`.
- [x] Verify the debugging tty on sys-usb -> I get no console.
- [x] Validate the file read on a USB storage from a Domain (direct mount) -> No business domain usable.
- [x] Validate the GUI display -> Not working

- Mosquitto does not start because of `mosquitto.conf` file syntax. The correct syntax is `include_dir /etc/mosquitto/conf.d` and it automatically loads the `.conf` files from that dir.
- In the log file `/var/log/safecor/vchan-sftp.log` on `sys-usb` there are python error. The client seems to try to connect to a TCP socket instead of a UNIX socket.
```
Traceback (most recent call last):
  File "/usr/lib/safecor/bin/safecor-vchan-sftp.py", line 174, in <module>
    main()
    ~~~~^^
  File "/usr/lib/safecor/bin/safecor-vchan-sftp.py", line 147, in main
    domains = query_direct_mount_domains()
  File "/usr/lib/safecor/bin/safecor-vchan-sftp.py", line 59, in query_direct_mount_domains
    Api().start(mqtt_client)
    ~~~~~~~~~~~^^^^^^^^^^^^^
  File "/usr/lib/python3.14/site-packages/safecor/_api.py", line 167, in start
    self.__mqtt_client.start()
    ~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/lib/python3.14/site-packages/safecor/_mqtt_client.py", line 137, in start
    self.mqtt_client.loop_start()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/usr/lib/python3.14/site-packages/paho/mqtt/client.py", line 2343, in loop_start
    self._sockpairR, self._sockpairW = _socketpair_compat()
                                       ~~~~~~~~~~~~~~~~~~^^
  File "/usr/lib/python3.14/site-packages/paho/mqtt/client.py", line 453, in _socketpair_compat
    sock1.connect(("127.0.0.1", port))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
OSError: [Errno 101] Network unreachable
```
- The business domains are stucked during their start and the console cannot be connected, probably because of the vchan connection script blocking (see preivous `sys-usb` fix)

### Root cause (Run 6)

1. **Mosquitto did not start.** The `mosquitto.conf` used an `include`
   directive, which is not valid mosquitto syntax, so the broker refused to
   start. The correct directive is `include_dir /etc/mosquitto/conf.d`
   (loads every `*.conf` file of the directory).
2. **paho-mqtt cannot start any client in a DomU.** paho 2.x creates the
   network-loop thread wake-up pipe with a **TCP socketpair over
   127.0.0.1** (`_socketpair_compat` in `loop_start()`), not a POSIX
   socketpair. DomUs have no loopback interface, so `loop_start()` raises
   `OSError: [Errno 101] Network unreachable` and every `Api().start()`
   fails (vchan-sftp, domain controllers, direct mount). This also explains
   the business domains stuck at boot: their controller crashes before the
   GUI comes up.
3. **Vchan ring data not in the shared namespace** —
   `/local/domain/system/vchan` does not exist. It must be verified where
   `vchan-socket-proxy` actually publishes the ring data (see the Run 7
   verification item) and the client/server paths adjusted accordingly.

### Quick fix applied

- [x] `mosquitto.conf`: `include` -> `include_dir /etc/mosquitto/conf.d`
- [x] `safecor` library (`_mqtt_client.py`): replace paho's `_socketpair_compat`
      with the POSIX `socket.socketpair()` (needs no loopback)
- [ ] Run 7: verify where the vchan ring data is published and adjust the
      client/server paths if needed

## Run 7

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

### Root cause (Run 7)

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

### Quick fix applied

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

## Run 8

Preparation:
- [x] Rebuild `safecor-core` package
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode

Verification:
- [x] Verify `/dev/gntdev` and `/dev/evtchn` are group `safecor`, mode `0660` -> They are both 660 and group root. They are in `/dev/xen`, not in `/dev`. 
- [x] Verify the `vchan-socket-proxy` servers are alive on Dom0 (full command line
      in `ps ax`, no `[vchan-socket-pr]` zombies). They are still zombies.
- [x] Verify `xenstore-ls /local/domain/system/vchan` lists one entry per domain
      (msg for all, input/tty for sys-usb) -> It does not exist.
- [x] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections -> It does not
- [x] Verify `/tmp/mqtt-*.sock` is connectable by `svc-vchan-tunnels`
      (`ls -l /tmp/mqtt-*.sock`; the fix adds `addgroup svc-vchan-tunnels mosquitto`
      and `chmod g+w /tmp/mqtt-*.sock` at service start) -> It was not but when I added `xen_gntalloc` it succesfully connected.
- [x] Verify MQTT communication between sys-usb and Dom0 (ping) -> No connection
- [x] Verify the boot is not blocked in every domain (sys-usb, business domains,
      sys-gui) -> still blocked.
- [x] Verify the debugging tty on sys-usb -> No connection
- [x] Validate the file read on a USB storage from a Domain (direct mount) -> cannot connect console to business domain
- [x] Validate the GUI display -> No GUI

Additional information:
- The module `xen_gntalloc` is mandatory to create the vchan. After `modprobe xen_gntalloc` and `chgrp safecor /dev/xen/gntalloc`, the vchan tunnels are created succesfully.
- When I run `xenstore-ls /local/domain/system/vchan` from inside `sys-usb` I get
```
xenstore-ls /local/domain/system/vchan
sys-usb = ""
 msg = ""
  ring-ref = "8"
  event-channel = "84"
 input = ""
  ring-ref = "9"
  event-channel = "85"
 tty = ""
  ring-ref = "10"
  event-channel = "86"
saphir-gui = ""
 msg = ""
  ring-ref:

xenstore-ls: xs_directory (/local/domain/system/vchan/saphir-gui/msg/ring-ref): Permission denied
```
which seems normal but the return code is 1 in this case. (The `Permission denied` on
the `saphir-gui` leaf is expected: each ring grants READ only to its peer domain, so a
sibling DomU cannot read another domain's `ring-ref`.)

### Root cause (Run 8)

Run 8 confirmed the device nodes live under `/dev/xen/` (not `/dev/`) and exposed two
defects in the Run 7 fix, plus a deeper third bug that is the real reason the business
domains are still stuck.

**1. Wrong device paths (the Run 7 fix no-oped).** The Run 7 fix ran
`chgrp safecor /dev/gntdev /dev/evtchn` and `chmod 660 ...`, but on Xen 4.19 the nodes
are `/dev/xen/gntdev` and `/dev/xen/evtchn`. The `chgrp`/`chmod` therefore targeted
nonexistent paths, the real nodes stayed group `root` mode `0660`, and
`svc-vchan-tunnels` still got `EACCES` — the servers remained zombies.

**2. Missing `xen_gntalloc` module.** The Dom0 server allocates the vchan ring page from
the grant allocator: `libxenvchan_server_init()` → `xengntshr_open()` →
`open("/dev/xen/gntalloc", O_RDWR)` (Xen `tools/libs/gnttab/linux.c`). The Run 7 fix
never loaded `xen_gntalloc`, so even with correct permissions the server could not open
`/dev/xen/gntalloc`. Manually confirmed: after `modprobe xen_gntalloc` +
`chgrp safecor /dev/xen/gntalloc` the rings were created and are visible in xenstore.

Device access (Xen 4.19, from `tools/libs/gnttab/linux.c` + `tools/libs/vchan/init.c`):

| side        | nodes opened                            | kernel modules           |
|-------------|-----------------------------------------|--------------------------|
| Dom0 server | `/dev/xen/gntalloc`, `/dev/xen/evtchn`  | `xen_gntalloc`, `xen_evtchn` |
| DomU client | `/dev/xen/gntdev`, `/dev/xen/evtchn`    | `xen_gntdev`, `xen_evtchn`   |

The DomU client runs as **root** (the `setup-vchan` initd has no `user=`), so the DomU
side is not blocked by permissions; only the Dom0 server side needs the `safecor` group
on the nodes.

**3. The `xs_watch` race — the real blocker.** This is why MQTT is still down and the
business domains are still stuck at boot, *even after* the device fix above.

The vchan **server** (Dom0) calls `libxenvchan_server_init()` **at service start**, which
creates the ring and writes `ring-ref`/`event-channel` to xenstore immediately. The Dom0
`create-vchan-tunnels` service starts right after the orchestrator registers the domain,
i.e. **before the DomU has finished booting**.

The vchan **client** (DomU) only sets up its xenstore watch lazily, inside
`connect_vchan()`, which runs **after a local app connects** to the client's UNIX socket
(`accept()` → `connect_vchan()` → `xs_watch(path)`). By that time (DomU booted + app
started) the ring **already exists**, because the Dom0 server created it earlier.

Xenstore watches are edge-triggered: `xs_watch(path)` only fires when the path is created
or modified *after* the watch is registered. Since the ring path already exists and is
never changed again, the watch **never fires**, and the client blocks forever in
`xs_read_watch()` → `libxenvchan_client_init()` is never called → no vchan connection →
no MQTT → business domain stuck at boot.

This also explains why the manual root test "worked": the Dom0 server was started
*after* the DomU client had already registered its watch, so the ring was created after
the watch and it fired. At real boot the order is reversed, so it deterministically
deadlocks.

### Quick fix applied (Run 8)

- [x] `create-vchan-tunnels.initd`: load `xen_gntdev`/`xen_gntalloc`/`xen_evtchn` and
      `chgrp safecor` + `chmod 660` on `/dev/xen/gntdev`, `/dev/xen/evtchn` and
      `/dev/xen/gntalloc` (each guarded by `[ -e ]`), before starting the service.

### Remaining blocker (requires a Xen patch)

The `xs_watch` race (bug 3) can only be fixed by patching `connect_vchan()` in Xen's
`tools/vchan/vchan-socket-proxy.c`: try `libxenvchan_client_init()` **immediately**
(before the watch loop), and only fall back to the watch if the ring does not exist yet.
This is a small patch that makes the client work whether or not the ring pre-exists. It
requires rebuilding the `xen-tools` package — **needs a decision on the Xen build**
(see Run 9).

> **Status (intermediate run 8-9): refuted.** The vchan `msg` tunnel works
> end-to-end at boot (the sftp script received the topology answer over MQTT),
> so the client connects fine when the ring pre-exists. No Xen patch is
> needed. The real remaining blocker is the permissions on the DomU bridge
> sockets (see the intermediate run 8-9 root cause below).

## Intermediate run 8-9

Actions:
- Changed the permissions on `/dev/xen/gntalloc` in Dom0
- Disabled hardening is `sys-usb`

Observations:
- The vchan tunnels start correctly in Dom0 (no zombie)
- When `sys-usb` starts it sends the request `system/topology/my_config/request` and Dom0 answers:
```
{"product_name": "Saphir", "use_usb": 1, "repository_disabled": false, "domains": [{"name": "sys-usb", "domain_type": 1, "direct_mount": false}, {"name": "saphir-gui", "domain_type": 2, "direct_mount": false}, {"name": "saphir-av-clamav", "domain_type": 2, "direct_mount": false}, {"name": "saphir-av-eset", "domain_type": 2, "direct_mount": false}], "direct_mount_domains": [], "screen": {"width": 800, "height": 1280, "rotation": 90, "enabled": 1, "default_focus": "saphir-gui"}, "languages": [], "default_language": "en", "pci_blacklist": []}
```
  - This command seems to be sent by the script `safecor-vchan-sftp`
- After that, in `sys-usb` the file `/var/log/safecor/vchan-sftp.log` contains: 
```
safecor-vchan-sftp: starting
safecor-vchan-sftp: no domains with direct_mount found in topology
```
- The `sys-usb controller` does not answer nor send any message
  - Maybe there is a conflicts between the controller and the `safecor-vchan-sftp` script for the access to the vchan?
  - Additional information: when I start the sys-usb controller manually with the command `python3 /usr/lib/safecor/bin/safecor-sys-usb-controller.py` it works well and messages are sent but when I start it with the command `/etc/init.d/safecor-sys-usb-controller start` the process is started but no message is sent. The difference is that when I run manually it is ran as `root` and the `initd` starts as `svc-sys-usb-controller`. When I run the command `su -s /bin/sh svc-sys-usb-controller -c '/usr/bin/python3 /usr/lib/sa
fecor/bin/safecor-sys-usb-controller.py'` I get the error `Could not connect to the MQTT broker on /var/run/safecor/mqtt.sock  [Errno 13] Permission denied`

Root cause:
- The error `[Errno 13] Permission denied` on `/var/run/safecor/mqtt.sock` is the
  blocker. The vchan `msg` bridge socket is created by `vchan-socket-proxy` (started
  as root by `setup-vchan.sh`) with mode `0755 root:root` — the Xen tool never
  chmods the socket. Connecting to a UNIX socket requires write permission on the
  socket file, so the `svc-*` users get `EACCES` and their MQTT connection never
  completes (`on_connect` never fires, no message is sent). Root bypasses the
  permission check, which explains the manual test result. `safecor-vchan-sftp`
  runs as root too, which is why it could query the topology.
- The controller/sftp conflict hypothesis is rejected: the `vchan-socket-proxy`
  client mode accepts multiple UNIX connections, each with its own vchan
  connection.
- Fix: `setup-vchan.sh` (both copies: `safecor-domu-base` and `safecor-sys-usb`)
  now waits for each socket to appear, then applies `chgrp safecor` + `chmod 660`.
  All `svc-*` users are already members of the `safecor` group (package
  post-installs), so no new users or groups are needed.
- Known limitation: if a `vchan-socket-proxy` process were restarted, the socket
  would be recreated with mode `0755` and nothing would re-apply the group
  permissions (no supervisor on these processes yet).

## Run 9

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

## Run 10

Preparation:
- [ ] Rebuild the `safecor-core` and `safecor-sys-usb` packages
- [ ] On Dom0: `apk update && apk add safecor-core`, then verify
      `apk info -v safecor-core` and `ls /etc/udev/rules.d/` (to rule out
      the "stale package" hypothesis)
- [ ] Full cold boot in debug mode

Verification:
- [ ] Verify `/dev/xen/gntdev`, `/dev/xen/evtchn`, `/dev/xen/gntalloc` are
      group `safecor`, mode `0660` right after boot (no manual fix)
- [ ] Verify the `vchan-socket-proxy` servers are alive with no restart
      loop (no `Permission denied` in `/var/log/safecor/vchan-servers.log`)
- [ ] Verify the input/tty servers are alive (no `connect: Permission
      denied`)
- [ ] Verify all domains (sys-usb, business, sys-gui) boot without hanging
- [ ] Verify the sys-usb controller sends `discover_components/response`
      and answers pings (via its initd, no manual relaunch)
- [ ] Verify the debug tty on sys-usb works
- [ ] Verify the file read on a USB storage from a Domain (direct mount)
- [ ] Verify the GUI display
