
# Run 3

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

## Root cause

`vchan_endpoint_exists()` checked if `xenstore-read /local/domain/<N>/data/vchan/msg`
returned a non-empty value. But the vchan path itself has an **empty value** — the data
is in sub-keys (`ring-ref`, `event-channel`). The check always returned `False`, so the
Dom0 never started the vchan client.

## Fix applied

- Changed `vchan_endpoint_exists()` to check the `ring-ref` sub-key instead:
  `xenstore-read /local/domain/<N>/data/vchan/<channel>/ring-ref`
- Added `after setup-vchan` dependency in `safecor-sys-usb-controller.initd` to ensure
  the vchan servers are up before the controller tries to connect to MQTT.
