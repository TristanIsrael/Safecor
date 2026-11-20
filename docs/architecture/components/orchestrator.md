# Orchestrator

> **Scope**: the Dom0 service that creates the Domains' environments and drives their lifecycle.
>
> **Last updated**: 2026-11-20
>
> **Main artifacts**: `orchestrator.initd` → `orchestrator.py` (Dom0), `create-domains.py`, `provision-domain.sh`, `start-sys-usb.sh`, `start-business-domain.sh`, the generated `/etc/safecor/xen/<name>.conf` files.

The orchestrator runs **unprivileged** as `svc-orchestrator`; a `doas` configuration permits it to run `xl`, `xenstore-read`, and the start scripts as root.

## Domain lifecycle

### Provisioning (one-time, at Dom0 install)

1. `finish-core-init.sh` creates `/usr/lib/safecor/{storage,packages}`, generates the PGP key, builds the local signed apk repository, patches QEMU (for GUI domains).
2. `create-domains.py` (`DomainsFactory.create_domains()`) for each domain in the topology:
   - `provision-domain.sh` — untars the `domu.apkovl.tar.gz` template, patches `etc/apk/world` + hostname, enables the `ttyS0` getty for HVM domains, and creates a 1 MB ext4 **config disk** (`/usr/lib/safecor/system/<name>-config.img`) holding the domain's apkovl.
   - `__create_xl_conf_domain()` — writes `/etc/safecor/xen/<name>.conf` (disks, vGPU/virtual inputs, PCI). No 9p shares and no `channel = [...]` — all inter-domain communication uses PV channels (vchan) bridged by `vchan-socket-proxy` at runtime (see [vchan-tunnel-manager.md](vchan-tunnel-manager.md)).
   - `__fetch_alpine_packages()` — fetches the domain's package into the local repo.
3. `create_packages_squashfs()` — packs the local repository into `/usr/lib/safecor/packages.squashfs` (the `xvde` disk of every DomU).

### Boot (every boot, `orchestrator.initd` → `orchestrator.py`)

1. Writes screen size/rotation to xenstore (`/local/domain/system/`).
2. Runs `set-xenstore-permissions.sh` (`xenstore-chmod -r /local/domain/system b`).
3. Creates per-domain virtual input devices (`uinput`).
4. PCI-passthrough USB controllers to `sys-usb` (`xl pci-assignable-add`).
5. Starts `sys-usb`: `doas start-sys-usb.sh` → `xl create -f /etc/safecor/xen/sys-usb.conf`.
6. Starts business domains: `doas start-business-domain.sh <name>` → `xl create -f /etc/safecor/xen/<name>.conf`.
   - For GUI domains: reads screen geometry from xenstore, positions the QEMU GTK window.

### DomU boot (inside the guest)

1. Non-GUI domains boot as **PVH** on the Dom0 kernel (`vmlinuz-safecor-virt`) + initramfs + modloop, with the apkovl read from the config disk (`apkovl=/media/xvdd/...` in the `extra` kernel line, `console=hvc0`). Rootfs is the shared `alpine-virt.iso` mounted as a read-only block device (`xvdc`).
   GUI domains boot as **HVM** from the `alpine-virt.iso` (CD-ROM, `devtype=cdrom`) with QEMU for GPU display; their console is the emulated serial port (`ttyS0` getty enabled at provisioning, `xl serial = "pty"`).
2. OpenRC `localmount` mounts `/mnt/packages` (squashfs) from `/etc/fstab`; the `modules` service loads the runtime kernel modules listed in the apkovl `/etc/modules` (the Xen vchan modules `xen_gntdev`/`xen_evtchn`/`xen_gntalloc` — the initramfs only carries the minimal boot set `loop, squashfs, ext4, xen_blkfront`, plus `sd-mod, usb-storage` for `sys-usb`).
3. `safecor-core-init` (boot runlevel) fixes permissions, runs `apk add` from `/mnt/packages`.
4. Domain-specific package post-install (e.g. `safecor-sys-usb`, `safecor-domu-base`).
5. `setup-vchan` (default runlevel) starts the local mosquitto broker of the domain (see [messaging.md](messaging.md)) and, for `sys-usb`, the `vchan-socket-proxy` clients (input, tty) connecting to the Dom0 vchan servers.
6. The controller process starts and connects to MQTT on the local broker's UNIX socket (`/var/run/safecor/mqtt.sock`).

## Xenstore key model

`/local/domain/system/` — Dom0 writes, all DomUs read:

| Key | Written by | Read by |
|-----|-----------|---------|
| `screen_size` | `orchestrator.initd` (fb0 virtual_size) | DomUs (`System._get_screen_size`) |
| `screen_rotation` | `write-screen-information-to-xenstore.py` | DomUs (`System.get_screen_rotation`) |
| `input-focus` | `orchestrator.py` | `start-business-domain.sh`, `InputsProxy` |
| `debug_on` | `debug.initd` | `safecor-sys-usb/hardening.sh`, `create-tty-tunnel.sh` (sys-usb tty bridge) |
| `domids/<name>` *(v2)* | orchestrator (after `xl create`) | DomUs (vchan peer discovery) |
| `vchan/<name>/<channel>/{ring-ref,event-channel}` *(v2)* | the `vchan-socket-proxy` server (Dom0; the server side creates the channel and grants read to the peer domain) | DomUs (`setup-vchan.sh`, vchan SFTP clients) |

Permissions: `set-xenstore-permissions.sh` grants recursive read + write (`b`) on the entire `/local/domain/system` subtree: the DomUs read these keys and the DomU-side vchan services write their channel nodes under `/local/domain/system/vchan`. Restricting the write grants to the vchan subtree only is tracked as a follow-up (issue #261).

## Domain disk layout

Generated `xl` configurations:

| vdev | Domain type | Target (Dom0) | Purpose |
|------|-------------|---------------|---------|
| `xvdc` | all | `alpine-virt.iso` (PVH: plain block disk, HVM: `devtype=cdrom`) | root ISO |
| `xvdd` / `sdd` | PVH / HVM | `/usr/lib/safecor/system/<name>-config.img` | apkovl (read by the initramfs) |
| `xvde` / `sde` | PVH / HVM | `/usr/lib/safecor/packages.squashfs` | local Alpine repository → `/mnt/packages` |
| `xvdf` / `sdf` | optional | `/usr/lib/safecor/tmp/<name>-swap.img` | swap |
| `xvdg` / `sdg` | optional | `/usr/lib/safecor/tmp/<name>-tmp.img` | temporary storage → `/tmp` |

**XL conventions**: PVH domains have **no** `devtype=cdrom` and use `console=hvc0` in the `extra` kernel line (PV console, reachable from Dom0 with `xl console <domid>`); HVM domains boot from the CD-ROM (`boot = "d"`) and use the SCSI vdevs `sdd`/`sde`/`sdf`/`sdg` (with `xvd*` vdevs qemu-xen refuses to start the domain with "qemu-xen doesn't support read-only IDE disk drivers"). HVM domains use `vga = "stdvga"`: virtio-gpu does not expose the physical resolution's mode, so the GUI display setup (`xrandr`) fails.

## vCPU allocation

Dom0 and `sys-usb` are not configurable (≈ 15 % of the system, shared, minimum 1 vCPU each): Dom0 takes the 2 first vCPUs (only the first one on a system with less than 4 CPUs), `sys-usb` takes the same vCPUs as Dom0. The remaining ≈ 75 % is split 20 % to `sys-gui` (overridable) and 80 % to the business Domains, divisible into the `vcpu.groups` ratios referenced by each domain's `vcpu_group`. See [../../specifications/topology.md](../../specifications/topology.md) for the topology fields.

## Related

- [vchan-tunnel-manager.md](vchan-tunnel-manager.md) — the vchan servers the generated xl configs no longer declare statically
- [inputs.md](inputs.md) — the virtual input devices created at step 3
- [display.md](display.md) — the GUI domain positioning (step 6)
