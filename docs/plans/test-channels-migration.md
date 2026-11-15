# Validation tests for the migration from channels to pvchan

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

- [ ] Rebuild `safecor-core` and `safecor-sys-usb` packages
- [ ] Refresh local Alpine repository on Dom0
- [ ] Boot in debug mode
- [ ] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb
- [ ] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0
- [ ] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections
- [ ] Verify MQTT communication between sys-usb and Dom0
