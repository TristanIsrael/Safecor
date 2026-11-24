# V2 Documentation Update — tracking plan

> **Purpose**: bring the project documentation (`docs/` + READMEs) and the Safecor Wiki up to date with the v2 architecture, after a full audit performed on 2026-11-24. Trigger: a product integrating Safecor is being upgraded from v1 to v2 — the documentation (especially the v1→v2 migration material) must be accurate before that upgrade.
>
> **Related issue**: #263 (Update the project documentation and the Safecor Wiki for the v2 architecture).
>
> **Audit basis**: code on branch `version-2` is the reference. Every finding below was verified against the code. The Wiki was audited from a clone of `TristanIsrael/Safecor.wiki` (37 pages).

## Status legend

| Status | Meaning |
|---|---|
| ⬜ Pending | not started |
| 🔧 In progress | being worked on |
| ✅ Done | implemented and committed |
| 🟡 Verified, commit pending | implemented and coordinator-verified against the code; the commit awaits explicit user confirmation |
| ⏸ Blocked | waiting on an external decision or dependency |

**Status as of 2026-11-24 (work session closed):** all items ✅. Phase 1 committed on the project's `version-2` branch as `78f7614` (one docs-only commit, 7 files; the user's staged `pyproject.toml` version change was left out of it). Phase 2 committed on the wiki's `version-2` branch as `1ce72f5` (migration guide + Python API rewrite), `b800a45` (page fixes) and `801dd17` (re-rendered diagrams) — **not pushed**, per user decision. Kanban #263 moved to *In review*. Full pytest non-regression run before the project commit: identical to the 22-failure baseline (403 passed).

## Phase 1 — Project documentation (`docs/` + READMEs, this repository)

| # | Item | Location | Category | Fix | Status |
|---|---|---|---|---|---|
| P1 | `project-status.md` is stale (last updated 2026-11-20): "runs 1–14; run 15 planned" (reality: runs 15–19), issue table states obsolete (#260/#262/#258/#264), `reboot_domain` "commented" (it is **active** via `doas /usr/lib/safecor/bin/reboot-domain.sh`, `_dom0_controller.py:287`), #241 "Open — console implemented" contradiction, #270–#274 absent | `docs/project-status.md` | Stale | Full refresh: active-version section, runs 15–19, current issue states, #270–#274 entries, `reboot_domain` active | ✅ |
| P2 | File API mis-attributed: "served by the core controller — `read_file`, `copy_file`, `delete_file`, `file_fingerprint`, `create_file`" — in fact **split**: Dom0 answers for the repository (`list_files`, `file_fingerprint`, `delete_file`); **sys-usb** answers for the USB disks (`copy_file`, `read_file`, `create_file`, `mount_file`, `unmount`) — `_sys_usb_controller.py:562-572` | `docs/architecture/overview.md:136` | Wrong | Rewrite the sentence with the correct split | ✅ |
| P3 | Same mis-attribution: `copy_file` and `create_file` listed as core-controller topics (they are SysUsbController topics) | `docs/architecture/components/core-controller.md:15` | Wrong | Move them to the sys-usb controller scope (or point to `sys-usb-controller.md`) | ✅ |
| P4 | `reboot_domain` "commented out / to be reworked with the libvirt removal" — the feature is **active** (`reboot-domain.sh` via doas); only the libvirt path is commented | `docs/architecture/components/core-controller.md:42` | Stale | State that the restart is active via the shell script; the libvirt path stays commented pending #265 | ✅ |
| P5 | DomU ISO name: `safecor-safecor-virt-x86_64.iso` → **`alpine-safecor-virt-x86_64.iso`** (symlink `alpine-virt.iso`; `safecor-core/APKBUILD:28,222`) | `docs/development/packaging.md:18` | Stale | Update the ISO table | ✅ |
| P6 | mkimage example uses `--tag v3.22` and Alpine `v3.21` repositories while v2 targets Alpine 3.24 | `docs/development/packaging.md:78-81` | Stale | Update the example to 3.24 | ✅ |
| P7 | `System` module-map line omits the direct-mount consumer API: `is_usb_mountpoint_ready()`, `on_usb_mountpoint_ready(cb)`, `get_current_domid()`, `get_domain_domid()` | `docs/specifications/python-api.md:86` | Missing | Extend the `_system.py` line with the USB-mountpoint + domid methods | ✅ |
| P8 | `conf.py` Sphinx `release = "1.2.0"` — the published API site (deployed on push to `main`) shows the v1 version and v1 content until `version-2` is merged into `main` | `python/lib/docs/source/conf.py:19` | Stale | Bump to `2.0.0` (takes effect when the docs CI builds from a v2 main) | ✅ |

**Verified fine (no change needed)**: `topology.md` (direct_mount, repository.disabled, 9p note), `protocol.md` (my_config, component states), `features.md` (direct mount, TP1), `python-api.md` module map (direct-mount manager, MountMode, NFR), mermaid sync rule (3/3 `.mmd` identical to the inline blocks), README en/fr structural sync, ADRs, design-rules, security-model, `overview.md` transport/storage sections.

**Commit rule**: one docs-only commit on `version-2`, message `docs: update the project documentation for the v2 architecture (#263)`. Never stage the run sheets (`run-17.md`, `run-18.md`, `run-19.md`, `test-channels-migration.md`).

## Phase 2 — Safecor Wiki (separate repository `TristanIsrael/Safecor.wiki`)

Work happens on a local clone; commit in the wiki repo is allowed (the diagram sync rule requires committing rendered images there), **push only on explicit user request**.

| # | Item | Page | Category | Fix | Status |
|---|---|---|---|---|---|
| W1 | **Create the `Migration-v1-v2.md` page** — referenced by `README.md:29` but **missing**; the key document for the product upgrade | new page | Missing | Full v1→v2 integration guide built from the impact map (appendix A): transport, storage, API, packages, topology, protocol, breaking changes, upgrade checklist | ✅ |
| W2 | **Rewrite `Python-api.md` completely** (user spec): (1) a short description of the API's role and how it works (singleton `Api`, asynchronous MQTT-based, the start/ready/subscribe sequence); (2) a link to the Sphinx API reference page; (3) a summary of the available functions grouped by purpose, each linking to its Sphinx anchor. Replace the Panoptiscan-era content entirely | `Python-api.md` | Obsolete-page | Full rewrite per the spec above | ✅ |
| W3 | No `my_config` topic, no direct-mount component; focus stale | `Protocol.md` | Missing/Stale | Add the `system/topology/my_config/{request,response}` section and the `safecor_direct_mount` component entry | ✅ |
| W4 | `direct_mount` field missing; the repository described as 9p-mounted in DomUs (9p is gone in v2 — file API + direct mount) | `Topology.md` | Stale/Missing | Add `domains[].direct_mount` (`{"mode":"ro"|"rw"}`), `repository.disabled`, the 9p-removal note | ✅ |
| W5 | No version column (v2 is 2.0-r0 for lib/core/domu-base/sys-usb); `safecor-domu-base` missing its v2 services (`setup-vchan`, `direct-mount`) and dependencies (`sshfs fuse3 xen mosquitto socat openrc shadow`); `safecor-sys-usb` missing `openssh-sftp-server bubblewrap setpriv` + user `svc-sys-usb-sftp` | `Packages.md` | Stale/Missing | Add versions, services, dependencies columns/notes | ✅ |
| W6 | `ALPINE_VERSION` "default 3.20" — in v2 it is **derived from `/etc/alpine-release`** (`safecor-core/conf/constants.sh:3`) | `Integration.md:66` | Stale | Update the constant's description | ✅ |
| W7 | "Currently empty"; no 2.0 line | `Changelog.md` | Stale | Add the v2 (2.0) entry: vchan migration, direct USB mount, local brokers, squashfs packages, versions | ✅ |
| W8 | The direct USB mount — the flagship v2 feature — is not mentioned | `Capabilities.md` | Missing | Add the direct mount capability | ✅ |
| W9 | Must state that the direct mount is **not** emulated (no SFTP/vchan emulation, `my_config` unemulated) | `Emulator.md` | Missing | Add the limitation note | ✅ |
| W10 | `create-mqtt-tunnels` → **`create-vchan-tunnels`**; 9p description; new user `svc-vchan-tunnels`; new udev rule `99-safecor.rules`; per-domain listeners | `Architecture.md`, `Safecor-core.md` | Stale | Update the Dom0 service list and architecture description | ✅ |
| W11 | Socket paths `/var/run/mqtt_msg_*.sock` → per-domain `/tmp/mqtt-<domain>.sock` (+ `/tmp/mqtt-dom0.sock`) | `Debugging.md` | Stale | Update the MQTT console paths | ✅ |
| W12 | Rendered architecture diagrams predate v2 (no direct mount, serial-era messaging) | `images/safecor-architecture-*.png/svg` | Stale | Re-render from `docs/diagrams/*.mmd` (`mmdc` with the repo theme) and replace the copies in the wiki (diagram sync rule) | ✅ |

**Wiki branch note (2026-11-24):** the wiki repository already has a **`version-2` branch** (tip `de6082c`, with prior work: the first `Migration-v1-v2.md` draft, the v2 architecture page + the renamed diagrams, `Edge.md`, the Graphical-design colors). All Phase 2 work was done **on that branch** (local clone `/tmp/opencode/safecor-wiki`, branch `version-2` tracking `origin/version-2`): it extends and corrects the prior work rather than starting from `master`. In particular: the branch's `Python-api.md` listed a **non-existent `DirectMountManager.start()`** method (replaced by the real public API `run`/`stop`/`is_mounted`/`get_mount_point`), and the `hld` + `lld-sftp-inputs` rendered images predated the latest `.mmd` sources (11-20 vs 11-22) and were re-rendered (`lld-messaging` was already identical). All changes are **uncommitted** and await explicit user confirmation.

**Verified fine (no change needed)**: `Languages.md`, `Licence.md`, `Roles.md`, `Sensors.md`, `Graphical-design.md`, `Design-rules.md`, `Security.md` (broadly), `Home.md` (broadly — re-check the diag version after W7).

### Audit corrections (do not apply these)

- ~~"`app-package` renamed to `package`"~~ — **wrong**: the topology JSON key is `app-package` (`_system.py:468`); only the parsed model attribute is `package`.
- ~~"`safecor-lib` is wrong, the package is now `safecor`"~~ — **conflation**: the **apk** package is still `safecor-lib`; the **Python module** is imported as `safecor`. Both statements are true at once.
- ~~"`depends` must contain `safecor-core`" is wrong~~ — **still valid** for the product's main (Dom0) package; `post-install.sh` still exists in v2.

### Sphinx site caveat (affects W2)

The API reference site (`https://tristanisrael.github.io/Safecor/`) is built by the docs CI **on push to `main` only** (`.github/workflows/documentation.yml`), and `conf.py` still says `release = "1.2.0"` — so it currently shows **v1 content**. It will regenerate for v2 automatically once `version-2` is merged into `main` (P8 bumps the version string). The W2 links point at the stable URLs (`api/safecor.generated.html` + `#safecor.<Class>` anchors), which will be correct after that merge.

## Out of scope (separate issues)

- The 16 unported 1.4-line features (#257) — documented in `docs/plans/unmerged-1.4-features.md`; the Migration guide lists them as "not in v2" without porting them.
- Running the hardware re-validation (run 19) — tracked in `docs/plans/test-channels-migration/run-19.md`.

## Appendix A — v1 → v2 integration impact map (verified against code)

### A.1 Transport

- Serial MQTT transport **removed**: `SerialMQTTClient`, `ConnectionType.SERIAL_PORT`, `/dev/hvc1`/`/dev/hvc2`, `DOMU_INPUT_SOCKET_FILEPATH`, QEMU `channel=[…]` chardevs. DomUs reach Dom0 **exclusively over vchan**.
- DomU: local **mosquitto broker** on `/var/run/safecor/mqtt.sock` (service **`setup-vchan`**, from `safecor-domu-base`); upstream bridge `safecor-<domain>-bridge` → socat `127.0.0.1:18860` → `vchan-socket-proxy` client. A local broker **multiplexes every local MQTT client** (v1 had one shared serial link).
- Dom0: service `create-mqtt-tunnels` → **`create-vchan-tunnels`** (`vchan-socket-proxy -m server` per (domid, channel); domain discovery via xenstore `/local/domain/system/domids`); new user **`svc-vchan-tunnels`**; new udev rule `99-safecor.rules` (gntdev/gntalloc/evtchn + uinput → group `safecor` 0660); `udev` enabled in the default runlevel.
- Dom0 broker listeners: 10 fixed `/tmp/mqtt_msg_1..10.sock` + `mqtt_msg_local/dom0.sock` → `/tmp/mqtt-local.sock` + `/tmp/mqtt-dom0.sock` + **per-domain-name** `/tmp/mqtt-<domain>.sock` generated from the topology (`generate-mosquitto-listeners.py`).
- `MqttClient` re-subscribes tracked topics after an automatic reconnection (v1 lost them).

### A.2 Storage / data exchange

- **9p shares removed**: the repository is **not mounted** in DomUs (the empty `/mnt/storage` dir is still created); file access goes through the **MQTT file API** (split: Dom0 for `__repository__` — `list_files`, `file_fingerprint`, `delete_file`; sys-usb for the USB disks — `copy_file`, `read_file`, `create_file`, `mount_file`, `unmount`) and the **direct USB mount**.
- Product packages: offline **`packages.squashfs`** read-only block disk at `/mnt/packages` (`xvde`), rebuilt at every Dom0 boot (v1: 9p share).
- DomU ISO: `safecor-safecor-virt-x86_64.iso` → **`alpine-safecor-virt-x86_64.iso`** (symlink `alpine-virt.iso`).
- DomU domain type: HVM+serial → **PV/PVH** for non-GUI domains (GUI stays HVM, `vga="stdvga"`).

### A.3 Direct USB mount (new in v2 — the flagship feature)

- A DomU with `direct_mount` in its topology mounts `/media/usb` over a **vchan SFTP channel** (sshfs; per-session **bwrap sandbox**, `setpriv` → `sftp-server`, account `svc-sys-usb-sftp`; per-domain wrappers in `/usr/lib/safecor/tmp` to stay under socat's 512-byte EXEC limit).
- The **`safecor_direct_mount`** component (states `STARTING`/`READY`/`OFF`, published by the sys-usb controller) is the **single synchronization point** (NFR-3: react to states, no polling).
- Consumer contract: `System.is_usb_mountpoint_ready()` / `System.on_usb_mountpoint_ready(callback)`; the `DirectMountManager` runs in each authorized DomU (service `direct-mount` from `safecor-domu-base`).
- The old `safecor-vchan-sftp` service is **deleted**; an upgrade hook removes it (`rc-service stop`, `rc-update del`).
- New one-shot query `system/topology/my_config/{request,response}`: `{}` → full topology; `{"domain_name": "<n>"}` → filtered. The `direct_mount_domains` field of the response is **global** (never filtered).
- **Not emulated** by `safecor-emulator` (no SFTP/vchan emulation; `my_config` unemulated) — a product using `direct_mount` cannot be emulated end-to-end.

### A.4 Public Python API (the `safecor` module, package `safecor-lib` 2.0-r0)

- **Added**: `MountMode` (`RO`/`RW`), `DirectMountManager`, `Topics.TOPOLOGY`/`Topics.MY_CONFIG`, `Constants.MQTT_VCHAN_SOCKET`/`INPUT_VCHAN_SOCKET`/`TTY_VCHAN_SOCKET`/`SAFECOR_DIRECT_MOUNT`, `System.get_current_domid()`, `System.get_domain_domid(name)`, `System.is_usb_mountpoint_ready()`, `System.on_usb_mountpoint_ready(cb)`, `ResponseFactory.create_my_config(topology, domain_name)`, `Domain.direct_mount`, `Topology.repository_disabled`. (Note: the one-shot `my_config` query is issued internally by the `DirectMountManager` — there is no public `Api.request_my_config()` method.)
- **Removed**: `SerialMQTTClient`, `ConnectionType.SERIAL_PORT`, `ResponseFactory.create_response_repository_path`, serial `Constants` (`/dev/hvc1`, `/dev/hvc2`, `DOMU_INPUT_SOCKET_FILEPATH`).
- **Changed**: `Constants.MQTT_MSG_BROKER_SOCKET` `/tmp/mqtt_msg_dom0.sock` → `/tmp/mqtt-dom0.sock`; `MqttFactory.create_mqtt_client_domu()` transport serial → UNIX socket. (Verified: `Domain.memory` default is 0 in both v1 and v2 — no change.)
- **Unchanged** (verified): `Api`, `Logger`, `ComponentsHelper`, `ConfigurationHelper`, `RequestFactory` signatures; all v1 MQTT topics and payloads (`disks/*`, `workflow/*`, `events/*`, `energy/*`, `settings/*`, `gui/switch`, `debugging/ping`, `sys-usb/clear-queues`).

### A.5 Topology (`/etc/safecor/topology.json`)

- **Added**: per-domain `business.domains[].direct_mount` = `{"mode": "ro"|"rw"}` (or `true` ⇒ `rw`); top-level `repository.disabled` (bool, default `false`).
- **Unchanged**: `usb`, `screen`, `vcpu`, `pci`, `storage`, `product`, `configurations` sections. Key names are code-authoritative: `screen.enabled`, `app-package`, `temp_disk_size`.
- Known trap: `safecor-tests/topology.json` is still v1.3 format (not parsed by the v2 loader).

### A.6 Packages

- Versions: `safecor-lib` 1.4-r1 → **2.0-r0**, `safecor-core` 1.4-r2 → **2.0-r0**, `safecor-domu-base` 1.4-r0 → **2.0-r0**, `safecor-sys-usb` 1.4-r0 → **2.0-r0**; the other packages unchanged; `arch` `noarch` → `all`.
- `safecor-domu-base`: depends `shadow` → `openrc shadow sshfs fuse3 xen mosquitto socat`; files + `init/direct-mount`, `init/setup-vchan`, `scripts/{setup-direct-mount.sh, start-direct-mount.py, setup-vchan.sh}`; rc-update `direct-mount default`, `setup-vchan default`.
- `safecor-sys-usb`: − `xe-guest-utilities`; + `openrc safecor-domu-base xen openssh-sftp-server bubblewrap setpriv` (+ `eudev socat fuse-archive fuse3 doas coreutils ntfs-3g`); files + `safecor-dm-channels.py` (doas root helper); new user `svc-sys-usb-sftp`; kernel modules + `usbcore fat usb-storage sd_mod … xen_gnt*`.
- `safecor-core`: + `squashfs-tools eudev`; `create-mqtt-tunnels` → `create-vchan-tunnels` (+ `generate-mosquitto-listeners.py`, `conf/99-safecor.rules`, `conf/safecor-listeners.conf`); new user `svc-vchan-tunnels`; apkovl 42 → 35 entries; `psec.rsa.pub` removed from the DomU apkovl.
- `safecor-gui-base`: − `xe-guest-utilities`, + `openrc xen`.
- Product packaging rule: product packages depend on `safecor-lib` + `safecor-domu-base` (+ `safecor-gui-base` for GUI DomUs).

### A.7 Breaking changes / removals summary (v1 product code that breaks)

1. Serial transport and `SerialMQTTClient`/`ConnectionType.SERIAL_PORT` — removed.
2. 9p shares (`/mnt/storage` in DomUs, 9p packages) — removed.
3. `ResponseFactory.create_response_repository_path` — removed.
4. `xe-guest-utilities` gone from the DomU images.
5. `safecor-vchan-sftp` service — deleted (upgrade hook cleans it).
6. `reboot_domain` (restart_domain) is now **active** from Dom0 (shell script) — v1 docs said unavailable.
7. 16 features of the 1.4 line are **not ported** to v2 (#257): `safecor-debug-tools`, hidden GRUB menu, raw NTFS recognition, same-name storage collisions, controller-stop notification, mouse-cursor hide, red debug console, syslog in sys-usb, chassis type in `system/info`, `disks/storage_info`, encrypted local storage, etc. — see `docs/plans/unmerged-1.4-features.md`.
8. Carried-over open bugs (same in v1 and v2): #217 (language list dropped), #218 (`list_files` name filter ignored), #220 (`storage_info`/`monitoring` unimplemented), #230 (`Api.publish` double-encode), #233 (subscriptions on reconnect — mitigated by re-subscribe, issue open).
9. `libvirt` is **still present** on Dom0 in v2 (removal is ADR 0005, backlog #265) — do not plan around its absence.

### A.8 Upgrade checklist (for a v1 product)

- [ ] Replace any use of the serial transport / `SerialMQTTClient` (DomU clients now use the local broker via `MqttFactory.create_mqtt_client_domu`).
- [ ] Replace any 9p-based file access (`/mnt/storage` reads) with the MQTT file API and/or the direct USB mount.
- [ ] Update package dependencies: `safecor-lib`/`safecor-domu-base` 2.0-r0 (+ `safecor-gui-base`); remove `xe-guest-utilities` if declared.
- [ ] Regenerate the topology: the v2 loader is authoritative (code key names); add `direct_mount` per domain if the product wants the USB; consider `repository.disabled`.
- [ ] React to the `safecor_direct_mount` component states (NFR-3) — do not poll.
- [ ] Use `System.is_usb_mountpoint_ready()` / `on_usb_mountpoint_ready(cb)` for USB readiness.
- [ ] Re-test on Alpine 3.24 (v2 tested base).
- [ ] Check the product against the "not ported" list (A.7.7) before promising 1.4 features.
