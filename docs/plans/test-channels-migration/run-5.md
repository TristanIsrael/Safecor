# Run 5

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

## Root cause

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

## Actions

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
