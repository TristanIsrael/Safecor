# Safecor — Architecture Reference

> **Status**: Draft (first edition, written to support the emulator operator-console work)
>
> **Last updated**: 2026-11-15
>
> **Audience**: developers working on the Safecor core and on Safecor-based products
>
> **Scope**: the "what" and "how" of the Safecor platform. §5 ("the emulatable surface") is the
>
> part that drives the emulator work — it lists every function the platform exposes and how it
>
> is provided, so an emulator (or its operator console) knows what to fake and how.

---

## 1. System context

Safecor is a **software architecture for building security products** (kiosk / embedded style)
on **Alpine Linux + Xen**. A product is a set of isolated virtual machines that talk to each
other over **MQTT**, supervised by a privileged management domain. The same code base runs the
core (on the appliance) and, through the **emulator**, on a plain development machine without
Xen or real hardware.

Three actors exist:

| Actor | Runs | Role |
|-------|------|------|
| **Dom0** (privileged) | Bare-metal / base domain | Control plane: repository, supervision, system info, workflow (shutdown / restart / GUI switch), logging. Hosts the `safecor` library's control side. |
| **Core DomU** (`sys-usb`) | Virtual machine | USB / disk / input controller: captures the USB PCI buses, lists/reads/copies/creates files on external disks and the repository, mount/unmount, and provides keyboard/mouse/touch input. |
| **Core DomU** (`sys-net`) | Virtual machine | *Not available yet* — would capture the network PCI buses (network cards) the same way `sys-usb` captures USB. |
| **Business DomU** | One VM per concern | The product's own applications (e.g. Saphir's `saphir-gui`, `saphir-av-clamav`, `saphir-av-eset`). They use the **API** to talk to the platform. |

**The fundamental rule**: domains never share memory. All cross-domain coordination is over
**MQTT topics** with JSON payloads. The only in-process coupling is inside a single domain.

> **Security posture**: PCI devices are considered dangerous and are captured by dedicated
> DomUs (`sys-usb` for USB, `sys-net` for network) using Xen PCI passthrough — which requires
> IOMMU (VT-d / AMD-Vi). The video display is captured by Dom0; Domains never touch it directly.

## 2. Deployment architecture

### 2.1 The topology file
The deployment is described by **`/etc/safecor/topology.json`** (one per product). It defines:
- `product` — name, splash background colour, `languages`, `default_language`.
- `usb` — `use` (enable the `sys-usb` domain).
- `screen` — `enabled`, `rotation`, `default_focus`.
- `pci` — `blacklist` (PCI buses to exclude).
- `vcpu.groups` — named vCPU allocation groups (ratios, see §2.4).
- `business.domains` — the business DomUs: `name`, `app-package`, `memory`, `has_gui`,
  `vcpu_group`, `temp_disk_size`, `swap_size`.
- `storage` — local storage: `type` (`disk`), `index`, `size` (MB, `-1` = all). *Note: this
  section is consumed by the core orchestrator; it is **not** parsed by the Python
  `System.__analyse_topology_struct` (see [`doc-sync-issues.md`](doc-sync-issues.md) T4).*
- `configurations` — hardware-specific overrides matched by a DMI identifier
  (`sys_vendor`, `product_name`), e.g. a specific laptop's screen rotation or PCI blacklist.

`System.get_topology()` (Dom0) loads the file, converts it to an internal struct
(`get_topology_struct`), parses it into a `Topology` object (`__parse_topology`), and applies
the matching hardware configuration (`ConfigurationHelper.apply_configuration`). The result is
the authoritative description of the running system: product name, screen, USB, languages,
default language, and the **domain list** (the core `sys-usb` domain plus the business domains).

> **Key names**: the canonical keys are the **code's** (`enabled`, `app-package`,
> `temp_disk_size`). The Wiki `Topology.md` tables use different names (`enable`, `package`,
> `temp_disk`) — see [`doc-sync-issues.md`](doc-sync-issues.md) T1–T3.

### 2.2 The shared repository
Domains exchange **data** through the **repository**, a staging area owned by the platform:
- `Constants.STR_REPOSITORY = "__repository__"` is the virtual disk name products use.
- On Dom0 it lives at `DOM0_REPOSITORY_PATH = /usr/lib/safecor/storage`; on a DomU it is
  mounted at `DOMU_REPOSITORY_PATH = /mnt/storage`.
- A product `read_file(source, path)` stages a file into the repository and triggers a
  `NEW_FILE` notification (with source + destination fingerprints).

**Package transport**: the generated `xl` configurations carry **no 9p shares anymore**.
The local Alpine repository is packed into a read-only `packages.squashfs` image on Dom0
(`create-packages-squashfs.sh`, rebuilt at every Dom0 boot) and attached to each DomU as a
plain block disk (`xvde`). The mount is declared in the DomU `/etc/fstab` (from the
`domu_apkovl.tmpl` overlay) and mounted at boot by OpenRC `localmount`.

The corresponding DomU `/etc/fstab` entry:
```
/dev/xvde  /mnt/packages  squashfs  ro  0 0
```

The 9p `storage` share of the repository is not exported either: file access for the DomUs
goes through the MQTT file API (served by the Dom0 controller) and the **direct USB mount**
(v2, see §2.4).

> **Note (v2)**: the repository 9p share will be made optional via
> `repository.disabled` in `topology.json` (see [`plans/direct-usb-mount.md`](plans/direct-usb-mount.md)).

### 2.3 Dom0 internal services
Dom0 is not only the `safecor` control side; it runs the whole orchestration stack
(Wiki `Safecor-core.md`):
- **Mosquitto** — the MQTT broker (core of the messaging).
- **Safecor vchan tunnels** — `create-vchan-tunnels.py` discovers DomUs in xenstore and runs
  `vchan-socket-proxy` servers that bridge each DomU's PV channels (msg, input, tty) to local
  UNIX sockets. The vchan data is published in the shared xenstore namespace
  `/local/domain/system/vchan/<domain name>/<channel>` (a DomU cannot read `/local/domain/0`).
  The `msg` channel connects directly to a Mosquitto broker UNIX listener named after the
  domain (`/tmp/mqtt-<domain name>.sock`); the per-domain listeners are generated from the
  product topology at install time (`generate-mosquitto-listeners.py`), along with the static
  `/tmp/mqtt-local.sock` (debug) and `/tmp/mqtt-dom0.sock` (Dom0) listeners. The `input` and
    `tty` channels connect to their respective local sockets in `/var/run/safecor/`. The
  servers run as `svc-vchan-tunnels`: creating a vchan requires opening the Xen device
  nodes (under `/dev/xen/` on Xen 4.19) — `gntalloc` (the server allocates the ring page
  from the grant allocator), `gntdev` (the client maps the ring page through the grant
  table) and `evtchn` (event channels, both sides). `safecor-core` therefore depends on
  `eudev` (started at boot), which applies `/etc/udev/rules.d/99-safecor.rules`: the
  `safecor` group gets read/write access to those nodes as soon as they are created, with
  no race between the module load and the permission setup (the rule also covers
  `uinput`). The service's initd loads the `xen_gntdev`/`xen_gntalloc`/`xen_evtchn`
  kernel modules and waits for the nodes to appear. The servers' standard error is logged in
  `/var/log/safecor/vchan-servers.log` and a server that exits is reaped and restarted by
  the discovery loop.
- **Safecor orchestrator** — creates the virtual inputs (keyboard/mouse/touch), the Xen config
  files, and starts the Domains.
- **Safecor inputs proxy** — filters and copies input data between the Domains and the physical
  inputs.
- **Safecor core controller** — the control side for shared services (the `Dom0Controller`).
- **Xorg** — window management; shows the display of the active (focused) GUI Domain.
- **QEMU** / **XEN backend** — virtual devices (disks, GPU) and the Xen block front/back
  ends.

### 2.4 User Domain (DomU) architecture
Each Domain is a **volatile** VM, re-created at every boot (stateless system):
- The root `/` is a **tmpfs** (RAM disk) — everything is destroyed when the Domain stops.
- Optional extra disks: a **swap disk** (image created before start, destroyed on stop) and a
  **temporary disk** mounted on `/tmp` (`temp_disk_size`).
- Automatically attached disks: the config disk (apkovl, `xvdd`) and the local Alpine
  package repository on `/mnt/packages` (`xvde` squashfs image, see §2.2).
- **Direct USB mount** (v2, optional): a DomU with `direct_mount` in its topology entry
  mounts `/media/usb` directly from `sys-usb` over a vchan+sshfs channel, bypassing the
  9p repository. Managed by `DirectMountManager` (see §4). The mount mode is controlled
  by the `direct_mount.mode` field (`ro` or `rw`).
- A GUI Domain (`has_gui: 1`) additionally gets a virtual keyboard, mouse and touch screen.

**vCPU allocation** (Wiki `Topology.md` "Resource management"): Dom0 and `sys-usb` are not
configurable (≈ 15 % of the system, shared, minimum 1 vCPU each); the remaining ≈ 75 % is split
20 % to `sys-gui` (overridable) and 80 % to the business Domains, divisible into the
`vcpu.groups` ratios referenced by each domain's `vcpu_group`.

### 2.5 Local storage & local Alpine repository
- **Local storage** — the repository backing store at `/usr/lib/safecor/storage` on Dom0.
  Created by `finish-core-init.sh` at Dom0 provisioning. Not shared to the DomUs: they use
  the MQTT file API and the direct USB mount (v2).
- **Local Alpine repository** — created during provisioning in
  `/usr/lib/safecor/packages`, signed with a local PGP key, packed into
  `packages.squashfs` and attached to each DomU as the `xvde` disk mounted on
  `/mnt/packages`. DomUs install their packages from this offline repository at boot.

### 2.6 Domain lifecycle (provisioning → boot → runtime)

**Provisioning** (one-time, at Dom0 install):
1. `finish-core-init.sh` creates `/usr/lib/safecor/{storage,packages}`, generates the PGP key,
   builds the local signed apk repository, patches QEMU (for GUI domains).
2. `create-domains.py` (`DomainsFactory.create_domains()`) for each domain in the topology:
   - `provision-domain.sh` — untars the `domu.apkovl.tar.gz` template, patches
     `etc/apk/world` + hostname, enables the `ttyS0` getty for HVM domains, and creates a
     1 MB ext4 **config disk** (`/usr/lib/safecor/system/<name>-config.img`) holding the
     domain's apkovl.
    - `__create_xl_conf_domain()` — writes `/etc/safecor/xen/<name>.conf` (disks,
      vGPU/virtual inputs, PCI). No 9p shares and no `channel = [...]` — all inter-domain
      communication uses PV channels (vchan) bridged by `vchan-socket-proxy` at runtime.
   - `__fetch_alpine_packages()` — fetches the domain's package into the local repo.
 3. `create_packages_squashfs()` — packs the local repository into
    `/usr/lib/safecor/packages.squashfs` (the `xvde` disk of every DomU).

**Boot** (every boot, via `orchestrator.initd` → `orchestrator.py`):
1. Writes screen size/rotation to xenstore (`/local/domain/system/`).
2. Runs `set-xenstore-permissions.sh` (`xenstore-chmod -r /local/domain/system r`).
3. Creates per-domain virtual input devices (`uinput`).
4. PCI-passthrough USB controllers to `sys-usb` (`xl pci-assignable-add`).
5. Starts `sys-usb`: `doas start-sys-usb.sh` → `xl create -f /etc/safecor/xen/sys-usb.conf`.
6. Starts business domains: `doas start-business-domain.sh <name>` → `xl create -f /etc/safecor/xen/<name>.conf`.
   - For GUI domains: reads screen geometry from xenstore, positions the QEMU GTK window.

**DomU boot** (inside the guest):
1. Non-GUI domains boot as **PVH** on the Dom0 kernel (`vmlinuz-safecor-virt`) + initramfs
    + modloop, with the apkovl read from the config disk (`apkovl=/media/xvdd/...` in the
    `extra` kernel line, `console=hvc0`). Rootfs is the shared `alpine-virt.iso` mounted as
    a read-only block device (`xvdc`).
   GUI domains boot as **HVM** from the `alpine-virt.iso` (CD-ROM, `devtype=cdrom`) with
   QEMU for GPU display; their console is the emulated serial port (`ttyS0` getty enabled
   at provisioning, `xl serial = "pty"`).
   OpenRC `localmount` mounts `/mnt/packages` (squashfs) from `/etc/fstab`; the `modules`
   service loads the runtime kernel modules listed in the apkovl `/etc/modules` (the Xen
   vchan modules `xen_gntdev`/`xen_evtchn`/`xen_gntalloc` — the initramfs only carries the
   minimal boot set `loop, squashfs, ext4, xen_blkfront`, plus `sd-mod, usb-storage` for
   `sys-usb`).
   `safecor-core-init` (boot runlevel) fixes permissions, runs `apk add` from
   `/mnt/packages`.
    Domain-specific package post-install (e.g. `safecor-sys-usb`, `safecor-domu-base`).
    `setup-vchan` (default runlevel) starts `vchan-socket-proxy` clients (msg, input, tty)
    connecting to the Dom0 vchan servers.
    Controller process starts, connects to MQTT over the vchan UNIX socket
    (`/var/run/safecor/mqtt.sock`).

**Xenstore key model** (`/local/domain/system/` — Dom0 writes, all DomUs read):

| Key | Written by | Read by |
|-----|-----------|---------|
| `screen_size` | `orchestrator.initd` (fb0 virtual_size) | DomUs (`System._get_screen_size`) |
| `screen_rotation` | `write-screen-information-to-xenstore.py` | DomUs (`System.get_screen_rotation`) |
| `input-focus` | `orchestrator.py` | `start-business-domain.sh`, `InputsProxy` |
| `debug_on` | `debug.initd` | `safecor-sys-usb/hardening.sh`, `create-tty-tunnel.sh` (sys-usb tty bridge) |
| `domids/<name>` *(v2)* | orchestrator (after `xl create`) | DomUs (vchan peer discovery) |
| `vchan/<name>/<channel>/{ring-ref,event-channel}` *(v2)* | the `vchan-socket-proxy` server (Dom0; the server side creates the channel and grants read to the peer domain) | DomUs (`setup-vchan.sh`, vchan SFTP clients) |

Permissions: `set-xenstore-permissions.sh` grants recursive read on the entire
`/local/domain/system` subtree, allowing any DomU to read these keys.

**Orchestrator privilege model**: the orchestrator runs unprivileged as `svc-orchestrator`;
a `doas` config permits it to run `xl`, `xenstore-read`, and the start scripts as root.

**Domain disk layout** (generated `xl` configurations):

| vdev | Domain type | Target (Dom0) | Purpose |
|------|-------------|---------------|---------|
| `xvdc` | all | `alpine-virt.iso` (PVH: plain block disk, HVM: `devtype=cdrom`) | root ISO |
| `xvdd` | all | `/usr/lib/safecor/system/<name>-config.img` | apkovl (read by the initramfs) |
| `xvde` | all | `/usr/lib/safecor/packages.squashfs` | local Alpine repository → `/mnt/packages` |
| `xvdf` | optional | `/usr/lib/safecor/tmp/<name>-swap.img` | swap |
| `xvdg` | optional | `/usr/lib/safecor/tmp/<name>-tmp.img` | temporary storage → `/tmp` |

XL conventions: PVH domains have **no** `devtype=cdrom` and use `console=hvc0` in the
`extra` kernel line (PV console, reachable from Dom0 with `xl console <domid>`); HVM
domains boot from the CD-ROM (`boot = "d"`) and keep `devtype=cdrom`.

**Debug TTY chain** (with `DEBUG=ON` on the Dom0 kernel command line, started by
`debug.initd`): the USB serial console cable is passed through to `sys-usb` and bridged
to a Dom0 getty:

```
host debug terminal → USB cable → sys-usb /dev/ttyUSB0 (udev rule 99-usbserial.rules)
  → socat (create-tty-tunnel.sh, supervised loop) → /var/run/safecor/tty.sock (vchan client)
  → vchan "tty" channel → vchan-socket-proxy server (Dom0)
  → /var/run/safecor/sys-usb-tty.sock (Dom0) → socat (debug.initd, PTY mode)
  → /var/run/safecor/tty-admin → getty (create-tty-terminal.sh) → Dom0 login
```

## 3. Communication (the MQTT protocol)

### 3.1 Transports
`MqttClient` supports two transports (`ConnectionType`):
- **UNIX socket** — used by both Dom0 (`/tmp/mqtt-dom0.sock`) and DomU
  (`/var/run/safecor/mqtt.sock`). On the DomU side, `vchan-socket-proxy` runs as a **client**
  that creates the local UNIX socket and connects to the Dom0 vchan server. On the Dom0 side,
  `create-vchan-tunnels.py` runs `vchan-socket-proxy` **servers** that connect directly to the
  Mosquitto broker UNIX listeners, named after the domain (`/tmp/mqtt-<domain name>.sock`) and
  generated from the product topology at install time. The vchan data lives in the shared
  xenstore namespace `/local/domain/system/vchan/<domain name>/<channel>`.
- **TCP on localhost** — `TCP_DEBUG`, development only. **This is what the emulator uses**
  (all peers and the product under test connect to a local `mosquitto` on port 1883).

### 3.2 Topic model
Topics use a `group/verb` structure (see `_topics.py`). Every **query/answer** pair uses the
suffixes `/request` and `/response`; **notifications** are published on a bare topic.

| Group | Topics (selected) |
|-------|-------------------|
| `system/disks` | `list_disks`, `list_files`, `read_file`, `copy_file`, `delete_file`, `file_fingerprint`, `create_file`, `new_file` (notif), `state` (disk state notif), `mount_file`, `unmount`, `deleted_file` (notif) |
| `system/workflow` | `shutdown`, `restart_domain`, `gui_ready` (notif) |
| `system/discover` | `components` (request/response) |
| `system/misc` | `ping` (keepalive), `benchmark` |
| `system/energy` | `state` (request/response) |
| `system/settings` | `changed` (notif), `languages/{list,default,current,set}` |
| `system/gui` | `switch` (request) |
| `system/events` | `error`, `warning`, `info`, `debug`, `set_loglevel`, `save_log` (logging) |
| `system/info` | (request/response) system information |
| `system/sys-usb` | `clear-queues` |
| `system/topology` | `my_config` (request/response — DomU queries its own topology config) |

### 3.3 The three message shapes
- **Request** — a command from a DomU to the platform (`RequestFactory` builds the payload).
  Published on `<topic>/request`.
- **Response** — the answer, published on `<topic>/response` (same topic, `/response` suffix).
- **Notification** — an asynchronous event with no expected reply (disk added, new file,
  setting changed, log line, error), published on a bare topic.

### 3.4 The API (`Api`, a singleton)
The `Api` is the **only** supported way for a DomU application to talk to the platform. It
wraps an `MqttClient` and is fully **asynchronous** — commands return immediately and results
arrive through callbacks:
- Lifecycle: `start()` → ready callback → `subscribe()` → subscribed callback → run.
- Command groups: **logging** (`debug/info/warn/error/critical`), **storage**
  (`get_disks_list`, `get_files_list`, `read_file`, `copy_file`, `delete_file`,
  `get_file_fingerprint`, `create_file`, `mount_file`, `unmount`), **discovery**
  (`discover_components`, `publish_components`), **system** (`request_energy_state`,
  `request_system_info`, `clear_sys_usb_queues`), **settings/languages**
  (`get_languages_list`, `get_default_language`, `get_current_language`, `set_current_language`),
  **workflow** (`shutdown`, `restart_domain`, `switch_gui`), **debugging** (`ping`),
  **notifications** (`notify_disk_added/removed`, `notify_gui_ready`).

`Api.start(mqtt_client, domain_identifier, recording, logfile)` also wires the `Logger`, so
every `Api().info(...)` is both logged locally and published on the `system/events/*` topics.

## 4. Core library components

`python/lib/src/safecor/` (imported as `safecor`):

| Module | Class(es) | Responsibility |
|--------|-----------|----------------|
| `_api.py` | `Api` | The DomU-facing asynchronous API (singleton) |
| `_dom0_controller.py` | `Dom0Controller` | Dom0-side command handler. **Dispatch**: linear `if/elif` chain in `__message_worker` matching topic strings to `__handle_*` methods; each message runs in its own thread. **Pattern to add a handler**: (1) define topic in `_topics.py`, (2) subscribe in `__on_mqtt_connected`, (3) add `elif` branch, (4) implement `__handle_*`. **Caveat**: the module-level `topology` global is **not populated** in the controller process (it's only populated in boot scripts like `create-domains.py`). |
| `_sys_usb_controller.py` | `SysUsbController` | Core DomU: real USB/disk controller (the emulator's `MockSysUsbController` stands in for it) |
| `_mqtt_client.py` | `MqttClient`, `ConnectionType` | MQTT transport (UNIX socket / TCP) |
| `_mqtt_factory.py` | `MqttFactory` | Creates a Dom0 or DomU client (incl. `create_mqtt_network_dev` for development) |
| `_system.py` | `System`, `topology` | System state (screen, UUID, CPU, memory), topology loading, settings, domain name. **Singleton** (`SingletonMeta` metaclass, no `__init__`, class-level cache). Also exports a **module-level global** `topology = Topology()` (populated by `System.get_topology()`). Xenstore reads via `subprocess.run(["xenstore-read", ...])`. |
| `_topology.py` | `Topology`, `Domain`, `Screen`, `Pci`, `DomainType` | Parsed topology model. **Not a singleton** — plain data class. `Domain` fields: `name`, `domain_type`, `memory`, `vcpus`, `cpu_affinity`, `package`, `has_gui`, `vcpu_group`, `temp_disk_size`, `swap_size`. Parsing is done by `System.__analyse_topology_struct` + `__parse_topology` (Topology never parses JSON itself). |
| `_configuration_helper.py` | `ConfigurationHelper`, `Configuration` | Applies the matching hardware configuration from the topology |
| `_request_factory.py` / `_response_factory.py` / `_notification_factory.py` | factories | Build the JSON payloads for requests / responses / notifications |
| `_topics.py` | `Topics` | The topic-name reference |
| `_constants.py` | `Constants`, `Settings`, `DiskState`, `ComponentState`, `InputType` | System-wide constants |
| `_logger.py` / `_syslogger.py` | `Logger`, `SysLogger` | Logging (local file + MQTT `system/events/*`) |
| `_file_helper.py` | `FileHelper` | File listing, fingerprinting (md5), folder traversal |
| `_disk_monitor.py` | `DiskMonitor` | inotify-based disk/file monitoring |
| `_inputs_daemon.py` / `_mouse.py` / `_keymap_fr.py` | `InputsDaemon`, `Mouse`, `KeymapFR` | Input (keyboard/mouse) handling |
| `_libvirt_helper.py` | `LibvirtHelper` | Xen/libvirt domain + CPU info |
| `_xenstore.py` | `XenStore`, `XsDomain`, `XsKey` | Xen xenstore via `xen.lowlevel.xs` (transactions for writes, `xs.watch` for monitoring). Currently only `XsDomain.System` resolves; other domains are a TODO. Not yet used by library code — the live consumers are the `xenstore-read` subprocess calls in `_system.py`. |
| `_xcb_controller.py` | `XcbController` | X11/XCB GUI focus control (switch GUI, hide/show) |
| `_tasks_runner.py` | `TaskRunner` | Background task execution |
| `_components_helper.py` | `ComponentsHelper` | Component discovery helpers |
| `_debugging.py` | `Debugging` | Debugging utilities |
| `_direct_mount_manager.py` | `DirectMountManager` | Manages the direct USB mount from sys-usb via vchan+sshfs. Runs as a standalone process in a DomU. Handles the full flow: query topology → discover domid → generate vchan script → mount via sshfs. |

## 5. The emulatable surface (what an emulator must provide)

This is the reference list for the operator-console work. Each row is a **function the platform
exposes**, where its data comes from on a real system, and how the emulator currently fakes it.
The operator console lets a human **drive the inputs** (scenario) and **observe the outputs**.

### 5.1 Environment / identity (provided by OS + topology)
| Function | Real source | Emulator today | Console control / observation |
|----------|-------------|----------------|-------------------------------|
| Product topology | `/etc/safecor/topology.json` → `System.get_topology()` | ✅ **served** at that path + parsed → `Environment` (Phase 0) | **Input**: load `topology.json` (Setup panel); pick a hardware configuration. **Observe**: topology summary (product, languages, screen, USB, business domains) in the state panel |
| System UUID | sysfs `/sys/class/dmi/id/product_uuid` | ✅ fake `open` (`SystemProfile.uuid`) | **Observe** |
| Screen size / rotation | xenstore `screen_size` / `screen_rotation` (`xenstore-read`) + fb0 `virtual_size` | ✅ fake `subprocess.run` + fake `open` | **Observe** (size/rotation from topology + profile) |
| CPU count / affinity | libvirt `get_cpu_count` / `get_domains` | ✅ fake `LibvirtHelper` (hard-coded Dom0 + sys-usb) | **Observe**; domains should reflect the topology's business domains |
| Memory / CPU freq / load | `psutil` | ✅ fake `psutil` (`SystemProfile`) | **Observe** |
| Boot time / uptime | `psutil.boot_time` | ✅ fake `psutil` | **Observe** |

### 5.2 Storage & disks (provided by `sys-usb`)
| Function | Real source | Emulator today | Console control / observation |
|----------|-------------|----------------|-------------------------------|
| List disks | `sys-usb` → `LIST_DISKS` response | ✅ `MockSysUsb` (local dirs) | **Observe** (live disk list) |
| Disk hot-plug / unplug | `DISK_STATE` notification (connected/disconnected) | ✅ `attach_disk` / `detach_disk` (scenario API) | **Control**: attach/detach; **Observe**: disk list + events |
| List files | `sys-usb` → `LIST_FILES` response | ✅ `MockSysUsb` | **Observe** |
| Read file (→ repository) | `sys-usb` copies to repo, `NEW_FILE` notif | ✅ `MockSysUsb` | **Observe** |
| Copy file (disk→disk) | `sys-usb` → `COPY_FILE` response | ✅ `MockSysUsb` | **Observe** |
| Create file (on a disk) | `sys-usb` writes to target dir | ✅ `MockSysUsb` | **Observe** |
| Delete file (repository) | `Dom0` removes from repo, `DELETED_FILE` notif | ✅ `MockDom0` | **Observe** |
| File fingerprint | `FileHelper.calculate_fingerprint` (md5) | ✅ (real `FileHelper` on local files) | **Observe** |
| Mount / unmount archive | `sys-usb` `mount_file` / `unmount` | ✅ `MockSysUsb` (real `mount`/`hdiutil`) | **Observe** |

### 5.3 System & workflow (provided by Dom0)
| Function | Real source | Emulator today | Console control / observation |
|----------|-------------|----------------|-------------------------------|
| System information | `Dom0` → `SYSTEM_INFO` response (`System.get_system_information`) | ✅ `MockDom0` (delegates to faked `System`) | **Observe** |
| Energy state (battery/plugged) | `Dom0` reads `psutil.sensors_battery` → `ENERGY_STATE` response | ✅ `MockDom0` (configurable `energy_level` / `plugged`) | **Control**: slider + AC switch + power off/on; **Observe** |
| Default / current language | `Dom0` settings (from topology `product.languages` / `default_language`) | ⚠️ `MockDom0` has an isolated `default_language`; **not wired to the topology** | **Control**: language combo; **Observe**: `SET_SETTING` / `SETTING_CHANGED` |
| Restart a domain | `Dom0` → `reboot-domain.sh` → `RESTART_DOMAIN` response | ✅ `MockDom0.record_restart` (records + responds accepted) | **Control**: domain name + button; **Observe**: restarted list |
| Shutdown | `Dom0` → `poweroff` → `SHUTDOWN` response | ⚠️ `MockDom0.request_shutdown` (records + responds accepted; no real poweroff) | **Control**: Shutdown button (W2); **Observe**: state + action timeline |
| GUI ready (hide splash) | `Dom0` kills the splash (`feh`) on `GUI_READY` | ⚠️ `MockDom0.notify_gui_ready` (responds accepted; no real splash kill) | **Control**: GUI-ready button (W4); **Observe**: action timeline |
| Switch GUI (focus) | `Dom0` `XcbController` show/hide | ⚠️ `MockDom0.request_switch_gui` (responds accepted; no real X11) | **Control**: Switch-GUI button (W5); **Observe**: action timeline |
| Component discovery | Dom0 + sys-usb → `DISCOVER_COMPONENTS` response | ✅ both mocks | **Observe** |
| Ping / keepalive | Dom0 / DomU → `PING` response | ✅ (Dom0 + sys-usb respond; `Emulator.ping` round-trip) | **Control**: ping target + data; **Observe**: result |
| Clear sys-usb queues | `sys-usb` `clear-queues` | ❌ **not implemented** in `MockSysUsb` | candidate |
| Get my config (topology) | Dom0 → `MY_CONFIG` response (full topology: domains, direct_mount, screen, languages) | ❌ **not implemented** in `MockDom0` | candidate |

### 5.4 Logging (provided by the `Logger`)
| Function | Real source | Emulator today | Console control / observation |
|----------|-------------|----------------|-------------------------------|
| Log levels (debug/info/warn/error/critical) | `Logger` → local file + `system/events/*` MQTT | ✅ (real `Logger` runs; peers publish via it) | **Observe**: platform-log journal |
| Set log level / save log | `system/events/set_loglevel`, `save_log` | ⚠️ partial | candidate |

### 5.5 Input (provided by the input daemon)
| Function | Real source | Emulator today | Console control / observation |
|----------|-------------|----------------|-------------------------------|
| Keyboard / mouse injection | `InputsDaemon` reads XenBus events | ✅ `FakeInputDevice` (XenBus wire format) | **Control**: (currently scenario API only; GUI injection optional) |

### 5.6 Coverage gaps (functions the emulator does NOT fake yet)
These are the platform functions a real product can call that the emulator currently **does not
answer** — a product exercising them would hang or get no response:

1. `clear_sys_usb_queues` (sys-usb) — not handled by `MockSysUsb`.
2. Business domains — not reflected in the fake `LibvirtHelper.get_domains()`.
3. Language settings — `MockDom0.default_language` is isolated from the topology
   (gated by the B1 / #217 code bug, see [`doc-sync-issues.md`](doc-sync-issues.md)).

Closed by the operator-console work (Phases 0-1): **topology serving** (`/etc/safecor/topology.json`
is now served + parsed → `Environment`) and the **`shutdown` / `gui_ready` / `switch_gui`
(W2/W4/W5)** fakes. The W2/W4/W5 fakes respond `accepted` but have **no real side effect** (no
poweroff, no splash kill, no X11 switch) — so they are listed as ⚠️ partial in
[`features.md`](features.md) rather than here.

**Documented but not implemented on the platform at all** (not just the emulator — see
[`doc-sync-issues.md`](doc-sync-issues.md) §2): `storage_info` (disk capacity query) and
`monitoring` (domain monitoring) are in the Wiki `Protocol.md` but have no topic or handler in
the code. **Out of scope** for the console unless the operator selects them.

The remaining gaps (clear-queues, business domains in libvirt, language settings) will be closed
as the operator selects those functions to emulate (see `plans/emulator-plan.md` §8).

## 6. How the emulator fits

The emulator (`python/emulator/src/safecor_emulator/`) reproduces the appliance **on a plain
machine, without Xen**, by three means that all keep the `safecor` library untouched:

1. **OS/hardware fakes** (`activate.py`) — patch the module-level OS touch-points of
   `safecor._system` (`psutil`, `LibvirtHelper`, `subprocess.run` for `xenstore-read`, and
   `open` for sysfs/proc). Driven by a `SystemProfile` dict. Installed from the outside and
   fully reversible (`uninstall_fakes`).
2. **Mock core peers** (`peers/`) — `MockDom0Controller` and `MockSysUsbController` answer the
   core MQTT commands over a local broker, operating on local directories instead of real
   hardware.
3. **A local broker** (`broker.py`) — an external `mosquitto` on TCP 1883, so the `safecor`
   clients (in `TCP_DEBUG` mode) and the product under test all connect to the same bus.

The `Emulator` orchestrator brings the three together (context manager) and exposes the
**scenario API**. The `safecor-emulator` CLI starts it standalone. The `pytest_plugin` exposes
it as a session fixture so a product's own test suite can drive the emulated core.

**The operator console** is a fourth layer on top: a QML window (`gui.py` + `qml/`) that runs
the `Emulator` in-process, takes a `topology.json` to shape the environment, and gives a human
the controls (scenario API) and the observation (state + journals) described in
[`plans/emulator-context.md`](../plans/emulator-context.md) §3. It is launched with
`safecor-emulator --gui --topology <topology.json>` (`cli.py` → `gui.run_gui`), and the headless
CLI is unchanged without `--gui`. The console UI is bilingual (**EN/FR**, switchable at runtime
from a header toggle); translations live in `i18n/{en,fr}.ts` (compiled to `.qm`) and the QML is
retranslated on change via `QQmlApplicationEngine.retranslate()`. The window and its bindings
are validated offscreen by `tests/test_gui.py` / `tests/test_i18n.py`. See
`plans/emulator-plan.md`.

## 7. Related documents

| Concern | Document |
|---------|----------|
| Function catalogue (what the platform exposes) | [`docs/features.md`](features.md) |
| Direct USB mount plan (v2) | [`plans/direct-usb-mount.md`](plans/direct-usb-mount.md) |
| Operator console guide (how to drive it) | [`docs/emulator-operator.md`](emulator-operator.md) |
| Code ↔ documentation sync issues | [`docs/doc-sync-issues.md`](doc-sync-issues.md) |
| Emulator session context | [`plans/emulator-context.md`](../plans/emulator-context.md) |
| Emulator operator-console plan | [`plans/emulator-plan.md`](../plans/emulator-plan.md) |
| Consumer (Saphir Phase 14) | `Saphir/docs/plans/refactoring-plan.md` §"Phase 14" |
| Public documentation | the **Safecor Wiki** (`Safecor.wiki/`) |
