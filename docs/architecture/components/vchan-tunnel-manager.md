# vchan tunnel manager

> **Scope**: the `vchan-socket-proxy` servers on Dom0 that bridge every DomU's PV channels (msg, input, tty, sftp) to local UNIX sockets.
>
> **Last updated**: 2026-11-25
>
> **Main artifacts**: `create-vchan-tunnels.py` (Dom0, discovery loop), the `vchan-socket-proxy` servers, `99-safecor.rules` (udev), the `safecor-vchan-tunnels` initd.

## What it does

`create-vchan-tunnels.py` discovers DomUs in xenstore and runs one `vchan-socket-proxy` **server** per (domain, channel) pair. The servers bridge each DomU's PV channels to local UNIX sockets:

| Channel | Dom0-side destination | Consumer |
|---------|----------------------|----------|
| `msg` | `/tmp/mqtt-<domain name>.sock` | the Dom0 Mosquitto broker (see [messaging.md](messaging.md)) |
| `input` | `/var/run/safecor/input.sock` | the orchestrator's inputs proxy (see [inputs.md](inputs.md)) |
| `tty` | `/var/run/safecor/sys-usb-tty.sock` | the debug tty terminal (see [sys-usb-controller.md](sys-usb-controller.md)) |
| `sftp` | a per-domain UNIX socket (`/var/run/safecor/direct-mount/vchan-<domain>.sock`) served in `sys-usb` by the `SysUsbController` (`safecor_direct_mount` component) | the SFTP server (see [direct-usb-mount.md](direct-usb-mount.md)) |

## Domid resolution (ADR 0006)

The vchan tunnel manager resolves the **live** domid for every domain on each
discovery-loop iteration, by scanning ``/local/domain/<N>/name`` in the Xen
tree.  This is the hypervisor-maintained source of truth (unforgeable).  The
cached domid at ``/local/domain/system/domids/<name>`` is demoted to a
**convenience cache**: it is updated in place only when the resolved live domid
differs from the cached value.  This self-heals the cache after domain
self-restarts (issue #275), preventing stale domid pinning.

The domid cache update path uses `xenstore-write`; the `svc-vchan-tunnels` user
needs a narrow doas grant for the cache path
(`/local/domain/system/domids/*`), defined in
`conf/doas-svc-vchan-tunnels.conf`.

The vchan data is published in the shared xenstore namespace `/local/domain/system/vchan/<domain name>/<channel>/{ring-ref,event-channel}` (a DomU cannot read `/local/domain/0`). The **server side creates the channel** at runtime and grants read access to the peer domain.

> **v1 → v2 change**: in v1 the channels were declared **statically** in the xl configs (`channel = [...]`, serial PV channels with a kernel frontend `/dev/hvc1`). In v2 the xl configs declare **no channels**: `msg`, `input`, `tty` and `sftp` are PV channels created **at runtime** by the `vchan-socket-proxy` servers in Dom0, with userspace clients in the DomUs (no hvc device).

## Privileges and kernel dependencies

The servers run as `svc-vchan-tunnels`. Creating a vchan requires opening the Xen device nodes (under `/dev/xen/` on Xen 4.19):

- `gntalloc` — the server allocates the ring page from the grant allocator.
- `gntdev` — the client maps the ring page through the grant table.
- `evtchn` — event channels, used by both sides.

`safecor-core` therefore depends on `eudev` (started at boot), which applies `/etc/udev/rules.d/99-safecor.rules`: the `safecor` group gets read/write access to those nodes as soon as they are created, with no race between the module load and the permission setup (the rule also covers `uinput`). The service's initd loads the `xen_gntdev`/`xen_gntalloc`/`xen_evtchn` kernel modules and waits for the nodes to appear.

## Robustness

- The servers' standard error is logged in `/var/log/safecor/vchan-servers.log`.
- A server that exits is reaped and restarted by the discovery loop.

## Follow-ups

- Issue **#261**: restrict the xenstore write grants to the `vchan` subtree only (today the whole `/local/domain/system` subtree is granted read + write to the DomUs — see [orchestrator.md](orchestrator.md)).
