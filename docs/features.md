# Safecor — Function & Non-Functional Requirements Reference

> **Status**: Reference (replaces the previous emulator-centric *Function Catalog*)
>
> **Last updated**: 2026-11-06
>
> **Platform version**: 1.4.0 (`safecor/__init__.py`)
>
> **Audience**: developers, product integrators and security auditors
>
> **Primary use**: the master list of **every function the Safecor platform exposes** and the
> **non-functional requirements (NFR)** the platform must satisfy.
>
> **Related**:
> - [`docs/architecture.md`](architecture.md) — how the platform is built (deployment, protocol, components).
> - [`docs/doc-sync-issues.md`](doc-sync-issues.md) — every Wiki ↔ code name/field mismatch and known bug.
> - [`docs/emulator-operator.md`](emulator-operator.md) — how to drive the emulator operator console.
> - Public documentation: the **Safecor Wiki** (`Safecor.wiki/`).

This document answers two questions:

1. **What can the platform do?** — a complete catalogue of functions, each classified as
   **coded**, **partial**, **documented-but-not-coded**, or **planned**.
2. **What must the platform guarantee?** — the non-functional requirements (security,
   performance, portability, maintainability, usability, data integrity).

---

## How to read this document

**Status legend**

| Icon | Meaning |
|------|---------|
| ✅ **coded** | Implemented in the code; a code reference (`file:line`) is given. |
| ⚠️ **partial** | Implemented but with a gap, a known bug, or a limited/no-op behaviour. |
| 📄 **doc'd, not coded** | Present in the Wiki but there is **no topic / no handler** in the code — a real platform gap, not just an emulator one. |
| 🚧 **planned** | Explicitly marked as future work / work-in-progress in the Wiki or code. |

**Provider legend**

| Provider | What it runs |
|----------|--------------|
| **core** | The `safecor-core` package: the Dom0 orchestration stack (shell/python scripts, orchestrator, MQTT tunnels, services). |
| **Dom0** | The privileged management domain; the `safecor` library control side (`Dom0Controller`). |
| **sys-usb** | The core DomU that captures the USB PCI buses (`SysUsbController`, `InputsDaemon`, `DiskMonitor`). |
| **product** | The business DomUs; they *consume* these functions through the `Api`. |

**Naming authority**: when the Wiki and the code disagree on a topic or field name, this
catalogue uses the **code's** name. Every mismatch is catalogued in
[`doc-sync-issues.md`](doc-sync-issues.md).

**Message shapes** (see architecture §3.3): *req/resp* = a `<topic>/request` answered by a
`<topic>/response`; *notif* = an asynchronous event on a bare topic; *cmd* = a request with a
workflow side effect.

---

# Part 1 — Functions

## 1.1 Boot & platform orchestration (provider: `core`)

The Dom0 orchestration stack. These run as OpenRC services / scripts from the `safecor-core`
package; they are **outside** the Python `safecor` library but are part of the platform.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| O1 | Boot & init sequence (XEN → kernel → OpenRC runlevels) | ✅ | Wiki `Boot-sequence.md`; `finish-core-init.sh` | Hardware discovery, AppArmor + security enforcement, X server, broker + tunnels start |
| O2 | Create Domain configurations from the topology | ✅ | `create-domains.py`; `System.get_topology()` | One VM per business domain + `sys-usb` |
| O3 | Domain lifecycle (create / start / stop / destroy) | ✅ | `orchestrator.py`, `start-business-domain.sh` | Pure lifecycle; Domains are **volatile**: root `/` is a `tmpfs`, re-created every boot. Swap/temp disks are managed separately (see T9, T10) |
| O4 | Create & sign the local Alpine repository | ✅ | `create-local-alpine-repository.sh`, `generate-pgp-keys.sh`, `reindex-and-sign-repository.sh` | Signed with a **local ephemeral PGP key** (private key removed after provisioning) |
| O5 | Encrypted local storage (create at boot, destroy at shutdown) | 🚧 | `integrity-setup.sh`; cryptsetup/LUKS | AES-512 XTS, **ephemeral key never written to disk** (see NFR S-ENC); work done but not finalized/validated |
| O6 | MQTT tunnels (proxy DomU sockets ↔ Mosquitto) | ✅ | `create-mqtt-tunnels.py`, `mosquitto` service | Filters and copies messages; core of the messaging |
| O7 | Orchestrator (start/monitor Domains, attach USB, create channels) | ✅ | `orchestrator.py` | Per-Domain message / log / input channels |
| O8 | Inputs proxy (filter/copy inputs between Domains and physical devices) | ✅ | core service `inputs proxy` | Pairs with `InputsDaemon` in `sys-usb` |
| O9 | Splash screen (product + core) | ✅ | `create-splash.py`, `create-splash` service, `feh` | Removed when the GUI reports ready (see W4) |
| O10 | Xorg window management / virtual display | ✅ | `start-x`, `generate-x-config.py` | Shows the focused GUI Domain in fullscreen |
| O11 | Publish screen size/rotation to XenStore | ✅ | `write-screen-information-to-xenstore.py`, `rotate-screen.py` | Read by DomUs (see T3) |
| O12 | Local Alpine repository share (`/mnt/packages`) + storage share (`/mnt/storage`) | ✅ | `provision-domain.sh` (9p) | Automatically attached to every Domain |

## 1.2 Topology & resource management (provider: `Dom0`)

Declared in `/etc/safecor/topology.json`, parsed into a `Topology` object by
`System.get_topology()`, then matched against a hardware configuration.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| T1 | Parse the product topology | ✅ | `_system.py` `get_topology` / `__analyse_topology_struct` / `__parse_topology` | product, languages, screen, USB, PCI blacklist, business domains |
| T2 | Match a hardware configuration (by DMI id) | ✅ | `_configuration_helper.py:33` `apply_configuration` | Compares `/sys/class/dmi/id/*`; overrides screen/USB/PCI (never product/domains/vcpu) |
| T3 | Screen size / rotation | ✅ | `_system.py` `get_screen_*` (XenStore `screen_size`/`screen_rotation`) | Fallback `1100,750` |
| T4 | System UUID | ✅ | `_system.py:124` `get_system_uuid` | From sysfs `product_uuid` (Linux) / `wmic` (Windows) / `ioreg` (macOS) |
| T5 | vCPU allocation per group | ✅ | `_system.py:485` `compute_vcpus_for_group` | 15 % to Dom0/sys-usb, rest split per `vcpu.groups` ratios |
| T6 | CPU pinning / affinity per group | ✅ | `_system.py:524` `compute_cpus_for_group` | Avoids CPU overlap between Domains |
| T7 | Settings from the kernel command line | ✅ | `_system.py:852` `parse_kernel_command_line_settings` | `debug=on`, `default_language`, `language` |
| T8 | Topology `storage` section (type/index/size) | 📄 | Wiki `Topology.md`; **not parsed** by `System` | Consumed by the core orchestrator only (see `doc-sync-issues.md` T4); to verify on GitHub |
| T9 | Domain swap disk | ✅ | topology `domains[].swap` | Per-Domain swap allocation |
| T10 | Domain temp disk | ✅ | topology `domains[].temp` | Per-Domain temporary storage |

## 1.3 Storage & disks (provider: `sys-usb`)

External-disk and file operations. In the emulator these run on local directories
(`MockSysUsbController`).

| # | Function | Status | Code / Wiki reference | Key payload / notes |
|---|----------|--------|-----------------------|---------------------|
| S1 | List connected disks | ✅ | `_sys_usb_controller.py:160` (`LIST_DISKS`), `FileHelper.get_disks_list` | resp: `disks[]` |
| S2 | Disk state (hot-plug / unplug) | ✅ | `DiskMonitor` (inotify, `_sys_usb_controller.py:92`); notif `DISK_STATE` | `disk`, `state` = connected / disconnected / mounted / unmounted |
| S3 | List files of a disk | ✅ | `_sys_usb_controller.py:172` (`LIST_FILES`) | req: `disk`, `recursive`, `from_dir`, `name_filters`; resp: `disk`, `files[]` |
| S4 | Read a file into the repository | ✅ | `_sys_usb_controller.py:194` (`READ_FILE`); notif `NEW_FILE` | Computes fingerprint, copies to repo, notifies |
| S5 | Copy a file disk→disk | 📄 | `_sys_usb_controller.py:238` (`COPY_FILE`) | resp: `filepath`, `status`, `fingerprint`; **not currently functional** (queued but not executed) |
| S6 | Create a file on a disk | ✅ | `_sys_usb_controller.py:301` (`CREATE_FILE`) | req: `disk`, `filepath`, `data` (base64, zlib if `compressed`); resp: `success`, `fingerprint` |
| S7 | Delete a file (disk) | ✅ | `_sys_usb_controller.py:353` (`DELETE_FILE`); notif `DELETED_FILE` | Repository deletions are handled by Dom0 instead |
| S8 | File fingerprint (MD5) | ✅ | `_sys_usb_controller.py:274` (`FILE_FINGERPRINT`), `FileHelper.calculate_fingerprint` (`_file_helper.py:159`) | resp: `fingerprint` |
| S9 | Mount an archive (ISO/VMDK/tar/…) | ✅ | `_sys_usb_controller.py:469` (`MOUNT_FILE`, `fuse-archive`) | read-only; extensions in `Constants.ARCHIVE_EXTENSIONS_HANDLED`; notif `DISK_STATE`(mounted) |
| S10 | Unmount a disk | ✅ | `_sys_usb_controller.py:519` (`UNMOUNT`, `fusermount3`) | notif `DISK_STATE`(unmounted) |
| S11 | Guest file formats (VMDK raw guest images) | 🚧 | `_sys_usb_controller.py:470` "guests files formats are not handled yet" | Only archives are mounted today |
| S12 | Clear sys-usb queues | ✅ | `_sys_usb_controller.py:462` (`SYS_USB_CLEAR_QUEUES`) | Drains read/copy queues |
| S13 | Disk capacity query (`storage_info`) | 📄 | Wiki `Protocol.md` "Request information about a disk" | **No topic, no handler** (`doc-sync-issues.md` U1, issue #220). Storage numbers are only embedded in system info (W1) |
| S14 | Read a file directly from a connected disk (without repository) | 📄 | — | Future function: bypass the repository, read directly from the mounted external disk |

## 1.4 Repository (provider: `Dom0`)

The shared staging area: virtual disk name `__repository__`
(`Constants.STR_REPOSITORY`); on Dom0 it lives at `/usr/lib/safecor/storage`, on a DomU at
`/mnt/storage`.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| R1 | List repository files | ✅ | `_dom0_controller.py:151` (`LIST_FILES`, repository only) | `disk == __repository__` |
| R2 | Delete a repository file | ✅ | `_dom0_controller.py:272` (`DELETE_FILE`); notif `DELETED_FILE` | — |
| R3 | Repository file fingerprint | ✅ | `_dom0_controller.py:163` (`FILE_FINGERPRINT`) | — |
| R4 | Get the repository mount path | ✅ | `_dom0_controller.py:305` (`REPOSITORY_PATH`) | resp: `path` = `/mnt/storage` |

## 1.5 System & workflow (provider: `Dom0`)

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| W1 | System information | ✅ | `_dom0_controller.py:267` (`SYSTEM_INFO`) → `_system.py:580` `get_system_information` | `core{version,debug_on}`, `system{os,machine{cpu,memory,load},storage,boot_time,uuid,cpu_allocation}` |
| W2 | Shutdown the system | ✅ | `_dom0_controller.py:186` (`SHUTDOWN` → `poweroff`) | resp: `state`(accepted/refused), `reason`; 5 s grace before poweroff |
| W3 | Restart a Domain | ✅ | `_dom0_controller.py:205` (`RESTART_DOMAIN` → `reboot-domain.sh`); `sys-usb` self-restart at `_sys_usb_controller.py:385` | Libvirt-based reboot is **commented out** ("coming feature"); Dom0 cannot be restarted |
| W4 | GUI ready (hide splash) | ✅ | `_dom0_controller.py:217` (`GUI_READY` → `killall feh`) | notif |
| W5 | Switch GUI focus | ✅ | `_dom0_controller.py:389` (`SWITCH_GUI` → `XcbController.show/hide_gui`) | req: `domain`; only one Domain has the focus |
| W6 | Start/stop periodic domain monitoring | 📄 | Wiki `Protocol.md` "Monitoring" | **No topic, no handler** (`doc-sync-issues.md` U2, issue #220/#227) |

## 1.6 Sensors & energy (provider: `Dom0`)

The platform's sensors are exposed over MQTT and queryable through the `Api` (Wiki `Sensors.md`).

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| E1 | Energy state (battery level + plugged) | ✅ | `_dom0_controller.py:259` (`ENERGY_STATE` → `psutil.sensors_battery`) | resp: `battery_level` (0–100), `plugged` (0/1) |
| E2 | Battery-level / energy-source polling | ✅ | Wiki `Sensors.md` (since v1.1) | Implemented through E1 |

## 1.7 Settings & languages (provider: `Dom0`)

The language list and default come from the topology (`product.languages`,
`product.default_language`); the current language is a runtime setting, optionally seeded from the
kernel command line (`language=`). All changes are propagated to every component via MQTT.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| L1 | List languages | ⚠️ | Handler `_dom0_controller.py:330`; topic `LIST_LANGUAGES` (`settings/languages/list`) | **Broken (B1 / #217)**: `Api.get_languages_list()` (`_api.py:629`) publishes to `settings/languages/request`, so the request is never matched by the handler |
| L2 | Get default language | ✅ | `_dom0_controller.py:333` (`DEFAULT_LANGUAGE`) | resp: `language` |
| L3 | Get current language | ✅ | `_dom0_controller.py:336` (`CURRENT_LANGUAGE`) | resp: `key`, `value` |
| L4 | Set current language | ✅ | `_dom0_controller.py:344` (`SET_LANGUAGE`) + notif `SETTING_CHANGED` | req: `language` |
| L5 | Setting changed | ✅ | notif `SETTING_CHANGED` (`_dom0_controller.py:368`) | `key`, `value` |

## 1.8 Component discovery & monitoring (provider: `Dom0` + `sys-usb` + `product`)

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| C1 | Discover components (query all states) | ✅ | `_dom0_controller.py:294` + `_sys_usb_controller.py:345` (`DISCOVER_COMPONENTS`) | resp: `components[]` of `{id, domain_name, label, type, state, version?, description?}` |
| C2 | Publish own components | ✅ | `Api.publish_components` (`_api.py:513`) | A product publishes its own component states |
| C3 | Component state change (listen) | ✅ | `DISCOVER_COMPONENTS` responses + `ComponentState` enum | This is the *only* monitoring primitive actually coded (see W6 for the periodic variant, not coded) |
| C4 | Monitor a file / directory (inotify) | ✅ | `_system.py:800` `monitor_file`, `DiskMonitor` | Internal helper, not an MQTT function |

## 1.9 Logging (provider: `Logger`, published by any Domain)

`Api().debug/info/warn/error/critical` publish on `system/events/*` **and** (when recording) the
`Logger` writes to a local file. A product can therefore observe the platform log over MQTT.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| G1 | Log an event (debug/info/warning/error/critical) | ✅ | `_logger.py:130-178`; topics `EVENTS/{debug,info,warning,error,critical}` | payload: `component`, `module`, `datetime`, `description` |
| G2 | Set the log level | ⚠️ | `_logger.py:197` (`SET_LOG_LEVEL`) | Handler updates the filter, but only when the client is subscribed to `system/events/#` (recording on); payload `level` |
| G3 | Save the log to a file (disk) | ⚠️ | `_logger.py:199` (`SAVE_LOG`) | Requires `recording=True`; republishes as a compressed `CREATE_FILE` request; payload `disk`, `filename` |
| G4 | OS-level logging (syslog) | ✅ | package `safecor-syslog` | `/var/log/safecor/system.log` |

## 1.10 Graphical user interface & display (provider: `Dom0`)

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| D0-1 | Multi-GUI Domains (since v3.1) | ✅ | `has_gui` in topology; `XcbController` | Several GUI Domains, one focused at a time |
| D0-2 | Switch the focused GUI | ✅ | See W5 | — |
| D0-3 | GUI-ready → remove splash | ✅ | See W4 | — |
| D0-4 | Splash screen | ✅ | See O9 | — |

## 1.11 Input (provider: `sys-usb`)

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| I1 | Keyboard / mouse / touch input | ✅ | `_inputs_daemon.py:48` (started by `SysUsbController`) | Reads `evdev` devices, serializes events on the XenBus `inputs` pv channel to the focused GUI Domain |

## 1.12 Debugging, diagnostics & benchmark (provider: `Dom0` / `sys-usb` / `core`)

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| B1 | Ping a Domain | ✅ | `_dom0_controller.py:309`, `_sys_usb_controller.py:376`, `Api.ping` (`_api.py:748`) | peer-to-peer topic `debugging/ping/<target>` |
| B2 | Keepalive ping | ⚠️ | topic `KEEPALIVE = misc/ping` (`_topics.py:42`) | Defined but **no controller subscribes to it** — orphan topic |
| B3 | Messaging throughput benchmark | ✅ | `_debugging.py:30` `Debugging.benchmark_messaging` | Client-side ping flood benchmark |
| B4 | I/O benchmark (`misc/benchmark`) | ⚠️ | handler `_sys_usb_controller.py:267` (no-op) | Subscription is **commented out** (`_sys_usb_controller.py:74`); handler validates args then returns |
| B5 | Debug mode (serial TTY / TTY tunnel) | ✅ | `create-tty-terminal.sh`, `create-tty-tunnel.sh` (only when `DEBUG=ON`) | 9600 8N1; root login if no password in topology |
| B6 | MQTT message/log inspectors | ✅ | `show-messages.sh`, `show-logs.sh` | Debug-mode helpers on the local socket |
| B7 | Diagnostic app (VT-x / VT-d compatibility) | ✅ | `python/diag` (PySide6 app), package `safecor-diag`, ISO | Checks virtualization + security capabilities before a Safecor product can run |

## 1.13 Provisioning & deployment infrastructure (provider: `core` / support infra)

How a Safecor product is installed and delivered.

| # | Function | Status | Code / Wiki reference | Notes |
|---|----------|--------|-----------------------|-------|
| P1 | Manual provisioning (USB install) | ✅ | Wiki `Provisioning.md` | Alpine + XEN + product from the official repository |
| P2 | Automatic provisioning (bootable product ISO) | ✅ | Wiki `Boot-from-ISO.md`, `setup/iso` (`mkimg.safecor.sh`) | `mkimage.sh --profile <pkg>`; embeds an app autostarted via `inittab` |
| P3 | Build Alpine packages (abuild / Docker) | ✅ | Wiki `Build-alpine-packages.md`, `setup/docker` | x86_64 output; signed repo |
| P4 | Deployment topologies (internet / local mirror / offline) | ✅ | Wiki `Support-infrastructure.md`, `sync_*` scripts | Mirrors kept up-to-date |
| P5 | Network boot (PXE) | 🚧 | infra exists (DHCP/TFTP/NFS, `deploy-infra-pxe.yml`); Wiki `Boot-from-network.md` **not written** | Capability present in the support infra, documentation pending |
| P6 | Containerized support infra (Docker/Ansible) | ✅ | `setup/infrastructure`, `docker-compose` | `network_boot` / `local_mirror` / `offline` profiles |

---

# Part 2 — Functions NOT coded / planned (explicit list)

A consolidated view of everything that is **documented in the Wiki but has no working
implementation** in the code, plus items that are coded but non-functional.

| # | Function | Status | Source | Code gap | Tracking |
|---|----------|--------|--------|----------|----------|
| N1 | Disk capacity query (`storage_info`) | 📄 | Wiki `Protocol.md` | No topic in `Topics`, no handler | #220 |
| N2 | Periodic domain monitoring (`system/monitoring`) | 📄 | Wiki `Protocol.md`, `Capabilities.md` | No topic, no handler | #220, #227 |
| N3 | "Monitoring" capability (listed as shipped since v1.0) | 📄 | Wiki `Capabilities.md` | Only component discovery exists (C1–C3) | #227 |
| N4 | "Resource attribution" capability | 📄 | Wiki `Capabilities.md` ("*cf topology*") | Stub section, no content | #227 |
| N5 | List languages end-to-end | ⚠️ | Wiki `Languages.md`, `Protocol.md` | Topic/handler exist but the API publishes to the wrong topic → requests dropped | #217 (B1) |
| N6 | I/O benchmark (`misc/benchmark`) | ⚠️ | Wiki `Protocol.md` (implied) | Handler is a no-op; subscription commented out | — |
| N7 | Keepalive ping (`misc/ping`) | ⚠️ | code `Topics.KEEPALIVE` | Orphan topic, no subscriber | — |
| N8 | Restart a Domain via libvirt | 🚧 | code `_dom0_controller.py:230` | Libvirt path commented ("coming feature"); uses `reboot-domain.sh` | — |
| N9 | Guest image mounting (VMDK raw) | 🚧 | `_sys_usb_controller.py:470` | "guests files formats are not handled yet" | — |
| N10 | `sys-net` Domain (network PCI capture) | 🚧 | Wiki `Architecture.md` | "currently not available" | — |
| N11 | Direct Domain↔Domain file link | 🚧 | Wiki `Architecture.md` (local storage) | "plans to add a direct link" | — |
| N12 | ARM64 architecture | 🚧 | Wiki `Home.md` | x86_64 only today | — |
| N13 | Topology `storage` section parsing | 📄 | Wiki `Topology.md` | Not parsed by the Python `System` (orchestrator-side only) | `doc-sync-issues.md` T4 |

---

# Part 3 — Non-Functional Requirements (NFRs)

The NFRs below are derived from the Wiki (`Design-rules`, `Security`, `Hardening`,
`Architecture`, `Diagnostics`, `Tested-hardware`, `Development`, `Graphical-design`) and from the
code. Each row gives the requirement, where it is stated, and where/how the platform addresses it.

## 3.1 Security (SCM — security maintenance)

| ID | NFR | Requirement | Source | Addressed by |
|----|-----|-------------|--------|--------------|
| S-ISO | Isolation | Every component lives in its own VM; components never share memory; no direct contact between components | Wiki `Security` | Xen domains; all coordination over MQTT |
| S-PROT | Protocol break | Use a minimal data protocol with a low attack surface; dangerous protocols (TCP/IP, USB) are confined to their capture Domain | Wiki `Security` | MQTT over serial/UNIX; `sys-usb`/`sys-net` capture PCI |
| S-STATE | Stateless system | The system has no persistent state; Domains are re-created every boot; immune to integrity tampering | Wiki `Design-rules` #8, `Architecture` | `tmpfs` root, ephemeral storage, no databases |
| S-ENC | Encrypted local storage | The shared storage image is encrypted and the key is ephemeral and never written to disk | Wiki `Security` "Local storage security" | cryptsetup/LUKS, AES-512 XTS, random key per boot; image destroyed at shutdown (O5) |
| S-SIGN | Package integrity & traceability | Every package is cryptographically signed and verified before install | Wiki `Security` "Packages tracability" | Alpine signatures + local ephemeral PGP key (O4) |
| S-IOMMU | Device isolation | IOMMU (VT-d / AMD-Vi) is **mandatory** for memory and device isolation | Wiki `Architecture`, `Diagnostics` | PCI passthrough in `sys-usb`; checked by the Diagnostic app |
| S-USER | Non-privileged services | `root` is never used; each service runs as its own user in group `safecor`; a service cannot read another's config | Wiki `Security` "Hardening rules" | service users, group `safecor`, file ownership |
| S-APPARMOR | Mandatory access control | AppArmor security profiles are active | Wiki `Hardening` (R45) | `safecor-hardening`, AppArmor at `boot` runlevel (O1) |
| S-HARDEN | System hardening | Apply the ANSSI GNU/Linux hardening reference (bootloader password, no auto module load, LSM Yama, disable IPv6, restrict `/boot`, etc.) | Wiki `Hardening` (R3–R79) | `safecor-hardening` package (auto-installed by `safecor-domu-base`) |
| S-BOOT | Boot chain security | Secured UEFI boot, measured boot, bootloader password, protected kernel command line | Wiki `Hardening` (R3, R5, R6) | GRUB/XEN config, `set-xenstore-permissions.sh` |
| S-SPEC | Speculation hardening | Mitigations for L1TF, Spectre v1/v2/v4, MDS, page-table isolation, page poisoning | Wiki `Hardening` (R8) | kernel compile/bootoptions |
| S-PCI | Dangerous-PCI containment | PCI devices are captured by dedicated DomUs; unwanted PCI buses can be blacklisted | Wiki `Architecture`, `Integration` | `sys-usb` capture, `pci.blacklist` in topology |
| S-DATA | Data remanence | No secret (private keys) or sensitive file persists after shutdown | Wiki `Security` "Analysis of the data lifecycle" | ephemeral keys, storage destroyed at shutdown (analysis "to be completed") |

## 3.2 Performance

| ID | NFR | Requirement | Source | Addressed by |
|----|-----|-------------|--------|--------------|
| P-LIGHT | Lightweight footprint | Small memory/disk footprint and fast boot | Wiki `Design-rules` #4, `Development` | Alpine (musl, BusyBox, OpenRC); vanilla Domain ≈ 86 MB RAM / 11.4 MB disk |
| P-VCPU | Deterministic resource allocation | vCPUs are allocated and **pinned** per Domain group to avoid overlap | Wiki `Topology` "Resource management" | `compute_vcpus_for_group`, `compute_cpus_for_group` (T5, T6) |
| P-MIN | Minimum hardware | 2 CPU cores, 1 GB RAM (4 GB for a large system), VT-x, IOMMU, HVM | Wiki `Diagnostics` "Minimum capabilities" | Checked by the Diagnostic app (B7) |
| P-9P | File-transfer tuning | 9p shares tuned for throughput (`msize`, `vm.*` sysctls) | Wiki `Development` "Notes" | `msize=131072`, `vfs_cache_pressure=200`, … |
| P-PKG | Bounded package size | GUI base package is large (MESA); document the cost | Wiki `Development` "Notes" | `safecor-gui-base` ≈ 373 MB (≈ 330 MB without MESA DRI) |

## 3.3 Portability & compatibility

| ID | NFR | Requirement | Source | Status |
|----|-----|-------------|--------|--------|
| PORT-ARCH | Target architecture | x86_64 only for now | Wiki `Home.md`, `Tested-hardware.md` | ✅ x86_64; 🚧 ARM64 in progress (N12) |
| PORT-OS | Base OS | Alpine Linux 3.20 / 3.21 (ISO example 3.21.x / 3.22) | Wiki `Provisioning.md`, `Development.md` | ✅ |
| PORT-DEV | Cross-platform development | Develop on Windows / GNU/Linux / macOS; build on x86_64 | Wiki `Development.md` | ✅ (Docker `safecor-dev` image) |

## 3.4 Maintainability & reliability (OCM — operational maintenance)

| ID | NFR | Requirement | Source | Addressed by |
|----|-----|-------------|--------|--------------|
| M-STD | Standard protocols | Rely on a mature, well-understood protocol | Wiki `Design-rules` #2 | MQTT |
| M-OTS | Off-the-shelf, mainstream components | Use mainstream-channel software (Alpine `main`/`community`) to inherit security fixes | Wiki `Design-rules` #1, #3 | Alpine packages |
| M-ROBUST | Robustness of critical components | CVE monitoring to confirm/reject critical components | Wiki `Design-rules` #5 | CVE process |
| M-API | Provision of an API | A simple, stable API for product integration | Wiki `Design-rules` #6 | `Api` (Python) + raw MQTT |
| M-DEBUG | Built-in debugging | Propagatable debug/status messages + serial capture + on-demand log export | Wiki `Design-rules` #7 | `Logger`, serial TTY (B5), `save_log` (G3) |
| M-CFG | Configuration management | Describe the whole system in `topology.json` (infra-as-code) | Wiki `Design-rules` #9 | Topology + `ConfigurationHelper` (T1, T2) |
| M-QUAL | Quality gates | Lint + type + security + coverage gates before release | Wiki `Tests.md`; `AGENTS.md` | `ruff`, `mypy`, `bandit`, `pip-audit`; coverage ≥ 80 % (Wiki) / 85 % (`AGENTS.md`) |
| M-VER | Versioning scheme | `MAJOR.MINOR.PATCH`; patch = fix, minor = feature, major = maintainer only | `AGENTS.md`, Wiki `Development.md` | SemVer-like rules; packages follow the version |

## 3.5 Usability

| ID | NFR | Requirement | Source | Addressed by |
|----|-----|-------------|--------|--------------|
| U-LANG | Multi-language | Define the available + default language in the topology; change the current language at runtime, propagated to all components | Wiki `Languages.md` | L1–L5 (⚠️ L1 broken — N5) |
| U-GUI | Graphical interface | A product can display its own GUI; switch focus between several GUI Domains; hide the splash when ready | Wiki `Architecture` "Virtual display" | `has_gui`, `switch_gui`, `gui_ready` (W4, W5, D0-1) |
| U-DESIGN | Graphical design | Consistent font (Bauhaus), color palette, and "Built on / Made with Safecor" badges | Wiki `Graphical-design.md` | design assets in `misc/` |

## 3.6 Data integrity

| ID | NFR | Requirement | Source | Addressed by |
|----|-----|-------------|--------|--------------|
| I-FP | File fingerprinting | Compute a fingerprint (MD5) on every read / write / copy / move of a file | Wiki `Capabilities` "Integrity" | `FileHelper.calculate_fingerprint` (S8), applied in read/copy/create (S4, S5, S6) |
| I-VERIFY | Fingerprint verification | The destination fingerprint must match the source; reported in the `NEW_FILE` notification | Wiki `Protocol.md` "New file" | `source_fingerprint` vs `dest_fingerprint` in the notification |

---

# Part 4 — Summary & coverage

**Function counts by area** (items that appear as rows in Part 1)

| Area | ✅ coded | ⚠️ partial | 📄 doc'd not coded | 🚧 planned |
|------|:--:|:--:|:--:|:--:|
| 1.1 Boot & orchestration | 11 | – | – | 1 (O5) |
| 1.2 Topology & resources | 9 | – | 1 (T8) | – |
| 1.3 Storage & disks | 10 | – | 3 (S5, S13, S14) | 1 (S11) |
| 1.4 Repository | 4 | – | – | – |
| 1.5 System & workflow | 5 | – | 1 (W6) | – |
| 1.6 Sensors & energy | 2 | – | – | – |
| 1.7 Settings & languages | 4 | 1 (L1) | – | – |
| 1.8 Discovery & monitoring | 4 | – | – | – |
| 1.9 Logging | 2 | 2 (G2, G3) | – | – |
| 1.10 GUI & display | 1* | – | – | – |
| 1.11 Input | 1 | – | – | – |
| 1.12 Debugging & diagnostics | 5 | 2 (B2, B4) | – | – |
| 1.13 Provisioning & deployment | 5 | – | – | 1 (P5) |
| **Total (Part 1 rows)** | **63** | **5** | **5** | **3** |

\* `1.10` — `D0-1` (multi-GUI) is the only *new* item; `D0-2`/`D0-3`/`D0-4` are aliases of
`W5`/`W4`/`O9` and are not counted twice.

**Consolidated gap list** — **Part 2 (N1–N13)** is the authoritative catalogue of everything
not fully working. It also lists *capability-level*
gaps that do not appear as Part 1 rows: `N3` (monitoring capability), `N4` (resource attribution),
`N8` (libvirt restart), `N10` (`sys-net`), `N11` (Domain↔Domain file link), `N12` (ARM64).

**Most important gaps to close**

1. **N5 / #217 (L1)** — the language-list request is dropped; blocks any language feature that
   lists available languages. One-line fix in `Api.get_languages_list()`.
2. **N1 / N2 (#220, #227)** — `storage_info` and `monitoring` are advertised in the Wiki but have
   no topic or handler; either implement them or remove them from the Wiki.
3. **N12 (ARM64)** — currently x86_64 only.
4. **N10 (sys-net)** — the network-capture Domain is not available; only `sys-usb` exists.

> **Note on code ↔ documentation drift**: several topic and field names in the Wiki differ from the
> code. This reference uses the **code's** names throughout. The full, itemized list of drift (with
> the authoritative side and the related GitHub issue) is in
> [`doc-sync-issues.md`](doc-sync-issues.md).
