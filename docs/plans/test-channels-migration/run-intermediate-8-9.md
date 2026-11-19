# Intermediate run 8-9

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