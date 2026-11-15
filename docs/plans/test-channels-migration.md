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
