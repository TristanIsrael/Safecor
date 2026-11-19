# Run 2

- [x] Rebuild `safecor-core` package
- [x] Boot in debug mode
- [x] Verify `xenstore-read /local/domain/system/domids/sys-usb` returns a numeric domid
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb -> It does not exist
- [x] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0 -> It does not exist
- [x] Verify `/var/log/safecor/vchan-tunnels.log` contains the discovery messages -> Contains `vchan-tunnels: starting discovery loop`
- [x] Verify MQTT communication between sys-usb and Dom0 -> no communication

## Root cause

`/etc/init.d/setup-vchan` does not exist in the sys-usb DomU. The `setup-vchan.sh`
script and `setup-vchan.initd` were only in `safecor-domu-base` (business domains),
but `sys-usb` uses `safecor-sys-usb` which does not depend on `safecor-domu-base`.

## Fix applied

- Added `setup-vchan.sh` and `setup-vchan.initd` to `safecor-sys-usb` package
- Added `rc-update add setup-vchan default` to `safecor-sys-usb` post-install
- Added `rc-update add setup-vchan default` to `safecor-domu-base` post-install