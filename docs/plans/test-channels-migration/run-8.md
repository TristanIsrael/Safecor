# Run 8

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

## Root cause (Run 8)

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

## Quick fix applied (Run 8)

- [x] `create-vchan-tunnels.initd`: load `xen_gntdev`/`xen_gntalloc`/`xen_evtchn` and
      `chgrp safecor` + `chmod 660` on `/dev/xen/gntdev`, `/dev/xen/evtchn` and
      `/dev/xen/gntalloc` (each guarded by `[ -e ]`), before starting the service.

## Remaining blocker (requires a Xen patch)

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