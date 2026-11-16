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
- [ ] Rebuild `safecor-core` (mosquitto.conf) and `safecor-lib` (paho socketpair fix) packages
- [ ] Refresh local Alpine repository on Dom0
- [ ] Boot in debug mode

Verification:
- [ ] Verify mosquitto starts on Dom0 (no config error in syslog)
- [ ] Verify the mosquitto listeners exist on Dom0: `/tmp/mqtt-dom0.sock`, `/tmp/mqtt-local.sock`, `/tmp/mqtt-sys-usb.sock`, and one per business domain
- [ ] Verify `/var/log/safecor/vchan-sftp.log` has no more paho traceback (the topology query succeeds)
- [ ] **Locate the vchan ring data** — on Dom0 run `xenstore-ls /local/domain/system/vchan`, `xenstore-ls /local/domain/0/data/vchan` and, for each DomU, `xenstore-ls /local/domain/<domid>/data/vchan`: the ring data must be found exactly once, and the client/server paths (`setup-vchan.sh`, `create-vchan-tunnels.py`, SFTP client scripts) must be aligned with where `vchan-socket-proxy` actually publishes it
- [ ] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb and in the business domains
- [ ] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections
- [ ] Verify MQTT communication between sys-usb and Dom0 (ping)
- [ ] Verify the boot is not blocked in every domain (sys-usb, business domains, sys-gui): `setup-vchan` and `safecor-vchan-sftp` return immediately and the domains fully boot
- [ ] Verify the debugging tty on sys-usb
- [ ] Validate the file read on a USB storage from a Domain (direct mount)
- [ ] Validate the GUI display
