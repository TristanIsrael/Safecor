# Run 6

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

## Root cause (Run 6)

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

## Quick fix applied

- [x] `mosquitto.conf`: `include` -> `include_dir /etc/mosquitto/conf.d`
- [x] `safecor` library (`_mqtt_client.py`): replace paho's `_socketpair_compat`
      with the POSIX `socket.socketpair()` (needs no loopback)
- [ ] Run 7: verify where the vchan ring data is published and adjust the
      client/server paths if needed