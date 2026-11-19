# Run 4

- [x] Rebuild `safecor-core` and `safecor-sys-usb` packages
- [x] Refresh local Alpine repository on Dom0
- [x] Boot in debug mode
- [x] Verify `/var/run/safecor/mqtt.sock` exists in sys-usb -> No
- [x] Verify `/var/run/safecor/sys-usb-msg.sock` exists on Dom0 -> Does not exist
- [x] Verify `/var/log/safecor/vchan-tunnels.log` shows client connections -> No
- [x] Verify MQTT communication between sys-usb and Dom0 -> There is no connection in the file
