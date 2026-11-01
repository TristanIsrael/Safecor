# Safecor — Function Catalog

> **Status**: Draft (first edition)
>
> **Last updated**: 2026-11-01
>
> **Audience**: developers and product integrators; **primary use**: the master list from
> which the functions to be emulated in the operator console are selected.
>
> **Related**: [`docs/architecture.md`](architecture.md) (how the platform is built),
> [`docs/doc-sync-issues.md`](doc-sync-issues.md) (code ↔ doc mismatches),
> [`plans/emulator-context.md`](../plans/emulator-context.md) (emulator session).

This document is the **complete catalogue of the functions the Safecor platform exposes** to
its Domains (through the `Api` / the MQTT protocol). For each function it records what it does,
who provides it, the message shape, the key payload fields, and — for the emulator work —
whether the emulator already fakes it.

**Legend (emulator support)**:
- ✅ **faked** — the emulator answers it today (a product calling it gets a valid response).
- ⚠️ **partial** — the emulator handles it but with a gap (isolated state, no side effect, …).
- ❌ **missing** — the emulator does not answer it (a product calling it would hang / get nothing).
- 📄 **documented, not implemented** — present in the Wiki but has **no topic/handler in the code**
  at all (a platform gap, not just an emulator one). See [`doc-sync-issues.md`](doc-sync-issues.md) §2.

> **Note**: several field/topic names in the Wiki differ from the code. This catalogue uses the
> **code's** names. Every code↔doc mismatch is catalogued in
> [`doc-sync-issues.md`](doc-sync-issues.md).

**Message shapes** (see architecture §3.2): *req/resp* = a `<topic>/request` answered by a
`<topic>/response`; *notif* = an asynchronous event published on a bare topic; *cmd* = a request
with a workflow side effect.

---

## 1. Storage & disks (provided by `sys-usb`)

External-disk and file operations. In the emulator these run on local directories
(`MockSysUsbController`).

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| S1 | List connected disks | `get_disks_list()` | `disks/list_disks` | req/resp | resp: `disks[]` | sys-usb | ✅ |
| S2 | Disk state (hot-plug/unplug) | `notify_disk_added/removed()` | `disks/state` | notif | `disk`, `state` (connected/disconnected/mounted/unmounted) | sys-usb | ✅ (scenario API `attach_disk`/`detach_disk`) |
| S3 | List files of a disk | `get_files_list(disk, recursive, from_dir, name_filters)` | `disks/list_files` | req/resp | req: `disk`, `recursive`, `from_dir`, `name_filters`; resp: `disk`, `files[]` | sys-usb | ✅ |
| S4 | Read a file into the repository | `read_file(disk, filepath)` | `disks/read_file` | req + notif | req: `disk`, `filepath`; notif `disks/new_file` | sys-usb | ✅ |
| S5 | Copy a file disk→disk | `copy_file(source_disk, filepath, destination_disk)` | `disks/copy_file` | req/resp | req: `disk`, `filepath`, `destination`; resp: `success`, `fingerprint` | sys-usb | ✅ |
| S6 | Create a file on a disk | `create_file(filepath, disk, contents, binary)` | `disks/create_file` | req/resp | req: `filepath`, `disk`, `data` (base64[, compressed]); resp: `success`, `fingerprint` | sys-usb | ✅ |
| S7 | Delete a file (disk) | `delete_file(filepath, disk)` | `disks/delete_file` | req + notif | req: `filepath`, `disk`; notif `disks/deleted_file` | sys-usb | ✅ |
| S8 | File fingerprint (md5) | `get_file_fingerprint(filepath, disk)` | `disks/file_fingerprint` | req/resp | req: `filepath`, `disk`; resp: `fingerprint` | sys-usb | ✅ |
| S9 | New file staged (repository) | — | `disks/new_file` | notif | `disk`, `filepath`, `source_fingerprint`, `dest_fingerprint` | sys-usb | ✅ |
| S10 | Mount an archive (ISO/VMDK/…) | `mount_file(disk, filepath)` | `disks/mount_file` | req + notif | req: `disk`, `filepath`; notif `disks/state` (mounted) | sys-usb | ✅ |
| S11 | Unmount a disk | `unmount(disk)` | `disks/unmount` | req + notif | req: `disk`; notif `disks/state` (unmounted) | sys-usb | ✅ |
| S12 | Clear sys-usb queues | `clear_sys_usb_queues()` | `sys-usb/clear-queues` | req/resp | — | sys-usb | ❌ |
| S13 | Disk capacity info | — | `disks/storage_info` | req/resp | req: `disk`; resp: `disk`, `total`, `used`, `free` | sys-usb | 📄 **documented, not implemented** |

> **📄 = documented in the Wiki but not implemented in the code** (no topic, no handler). See
> [`doc-sync-issues.md`](doc-sync-issues.md) §2. Such functions are **out of scope** for the
> emulator/console unless explicitly selected.

## 2. Repository (provided by Dom0)

The shared staging area (`__repository__`, `/usr/lib/safecor/storage` on Dom0).

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| R1 | List repository files | `get_files_list("__repository__", …)` | `disks/list_files` | req/resp | same as S3, disk = `__repository__` | Dom0 | ✅ |
| R2 | Delete a repository file | `delete_file(filepath, "__repository__")` | `disks/delete_file` | req + notif | same as S7; notif `disks/deleted_file` | Dom0 | ✅ |
| R3 | Repository file fingerprint | `get_file_fingerprint(filepath, "__repository__")` | `disks/file_fingerprint` | req/resp | same as S8 | Dom0 | ✅ (real `FileHelper` on the local repo dir) |

## 3. System & workflow (provided by Dom0)

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| W1 | System information | `request_system_info()` | `system/info` | req/resp | resp: `core{version,debug_on}`, `system{os,machine{arch,cpu,memory,load},boot_time,uuid,storage}` | Dom0 | ✅ (delegates to the faked `System`) |
| W2 | Shutdown | `shutdown()` | `workflow/shutdown` | cmd/resp | resp: `state` (accepted/refused), `reason`; then `poweroff` | Dom0 | ❌ |
| W3 | Restart a domain | `restart_domain(domain_name)` | `workflow/restart_domain` | cmd/resp | req: `domain_name`[, `forced`]; resp: `domain_name`, `state`, `reason`; then `reboot-domain.sh` | Dom0 | ⚠️ (records + responds accepted; no real restart) |
| W4 | GUI ready (hide splash) | `notify_gui_ready()` | `workflow/gui_ready` | notif | — ; Dom0 kills the splash (`feh`) | Dom0 | ❌ |
| W5 | Switch GUI focus | `switch_gui(domain_name)` | `gui/switch` | cmd | req: `domain`; Dom0 `XcbController` hides current + shows target | Dom0 | ❌ (no X11 in the emulator) |
| W6 | Monitor domains (start/stop) | — | `monitoring` | req/resp | req: `operation`, `target`, `delay`; resp: `domain`, `operation`, `accepted` | Dom0 | 📄 **documented, not implemented** |

## 4. Energy (provided by Dom0)

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| E1 | Energy state (battery/plugged) | `request_energy_state()` | `energy/state` | req/resp | req: — ; resp: `battery_level` (0-100), `plugged` (0/1) — real: from `psutil.sensors_battery` | Dom0 | ✅ (configurable `energy_level`/`plugged`; scenario API `set_energy_state`/`power_off`/`power_on`) |

## 5. Settings & languages (provided by Dom0)

The language list and default come from the topology (`product.languages`,
`product.default_language`); the current language is a runtime setting, optionally seeded from
the kernel command line.

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| L1 | List languages | `get_languages_list()` | `settings/languages/list` | req/resp | resp: `languages[]` (from topology) | Dom0 | ❌ (not subscribed by `MockDom0`) |
| L2 | Get default language | `get_default_language()` | `settings/languages/default` | req/resp | resp: `language` | Dom0 | ⚠️ (isolated `default_language`, not wired to the topology) |
| L3 | Get current language | `get_current_language()` | `settings/languages/current` | req/resp | resp: `key`, `value` | Dom0 | ❌ |
| L4 | Set current language | `set_current_language(lang)` | `settings/languages/set` | cmd/resp + notif | req: `language`; resp: `key`,`value`; notif `settings/changed` | Dom0 | ❌ |
| L5 | Setting changed | — | `settings/changed` | notif | `key`, `value` | Dom0 | ❌ |

## 6. Component discovery (provided by Dom0 + sys-usb)

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| C1 | Discover components | `discover_components()` | `discover/components` | req/resp | resp: `components[]` of `{id, domain_name, label, type, state, version?, description?}` | Dom0 + sys-usb | ✅ (both mocks respond) |
| C2 | Publish own components | `publish_components(components)` | `discover/components` | resp | product publishes its own component states | (product) | n/a (product side) |

## 7. Logging (provided by the `Logger`, published by Dom0 / DomUs)

`Api().debug/info/warn/error/critical` write to the local log file **and** publish on the
`system/events/*` topics. A product can therefore observe the platform log over MQTT.

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| G1 | Log message | `debug/info/warn/error/critical(message, module)` | `events/{debug,info,warning,error}` | notif | `level`, `message`, `module`, timestamp | Logger (any domain) | ✅ (real `Logger` runs; the platform-log journal will capture these) |
| G2 | Set log level | (request) | `events/set_loglevel` | req/resp | req: `level` | Dom0 | ⚠️ |
| G3 | Save log to a disk | (request) | `events/save_log` | req/resp | req: `disk`, `filename` | Dom0 | ⚠️ |

## 8. Debugging & benchmark (provided by Dom0 / sys-usb)

| # | Function | API method | Topic | Shape | Key payload fields | Provided by | Emulator |
|---|----------|-----------|-------|-------|--------------------|-------------|----------|
| D1 | Ping a domain | `ping(target_domain, data)` | `debugging/ping/<target>` | req/resp | req: `id`, `source`, `data`, `sent_at`; resp echoes them | Dom0 / sys-usb / DomU | ⚠️ (sys-usb + product respond; Dom0 mock partial) |
| D2 | Keepalive ping | — | `misc/ping` | req/resp | — | Dom0 | ⚠️ |
| D3 | I/O / inputs benchmark | (request) | `misc/benchmark` | req/resp | req: `module` (`inputs`/`files`) | sys-usb | ❌ (handler present, no-op) |

## 9. Input (provided by the input daemon)

| # | Function | Source | Direction | Notes | Emulator |
|---|----------|--------|-----------|-------|----------|
| I1 | Keyboard / mouse events | `InputsDaemon` reads XenBus input events | into the focused GUI domain | The emulator's `FakeInputDevice` produces XenBus wire-format events | ✅ (scenario API `inject_key`/`mouse_click`/…; GUI-driven injection optional) |

## 10. Topology & environment (provided by OS + the topology file)

Not MQTT functions — these are read from the OS / `topology.json` and shape the system. They
are the **inputs** the operator console will let a human define.

| # | Function | Real source | Notes | Emulator |
|---|----------|-------------|-------|----------|
| T1 | Product topology | `/etc/safecor/topology.json` → `System.get_topology()` | product name, languages, default language, screen, USB, PCI, business domains, hardware configurations | ❌ (not served; flat `SystemProfile` used instead) |
| T2 | System UUID | sysfs `product_uuid` | identity | ✅ (fake `open`) |
| T3 | Screen size / rotation | xenstore `screen_size`/`screen_rotation` + fb0 | display geometry | ✅ (fake `subprocess.run`/`open`) |
| T4 | CPU count / affinity | libvirt | compute | ✅ (fake `LibvirtHelper`, hard-coded domains) |
| T5 | Memory / freq / load | `psutil` | resources | ✅ (fake `psutil`) |
| T6 | Boot time / uptime | `psutil.boot_time` | elapsed | ✅ (fake `psutil`) |

---

## 11. Summary — what the emulator covers today

| Area | Faked ✅ | Partial ⚠️ | Missing ❌ | Doc'd not impl. 📄 |
|------|----------|-----------|-----------|--------------------|
| Storage & disks (sys-usb) | S1-S11 | — | S12 (clear-queues) | S13 (storage_info) |
| Repository (Dom0) | R1-R3 | — | — | — |
| System & workflow (Dom0) | W1 | W3 (restart) | W2 (shutdown), W4 (gui_ready), W5 (switch_gui) | W6 (monitoring) |
| Energy (Dom0) | E1 | — | — | — |
| Settings & languages (Dom0) | — | L2 (default) | L1, L3, L4, L5 | — |
| Component discovery | C1 | — | — | — |
| Logging | G1 | G2, G3 | — | — |
| Debugging & benchmark | — | D1, D2 | D3 (benchmark) | — |
| Input | I1 | — | — | — |
| Topology & environment | T2-T6 | — | T1 (topology serving) | — |

> **Language settings caveat**: the whole L-group is at risk because of the code bug
> [`doc-sync-issues.md`](doc-sync-issues.md) B1 / issue #217 — the language **list** request is
> never processed by the Dom0 handler, so `L1` (and the language combo in the console) cannot be
> validated end-to-end until that is fixed.

**Core gaps to close for the operator console** (driven by the topology decision, see
`plans/emulator-plan.md` Phase 0): **T1** (serve + parse `topology.json`), the **business
domains** in T4, and **L1-L5** (languages wired to the topology, **gated by B1/#217**). The
remaining ❌ items (W2, W4, W5, S12, D3) are **optional** and are only emulated if the operator
selects them in the function-set decision (see `plans/emulator-context.md` §5 and
`plans/emulator-plan.md` §8). The 📄 items (S13, W6) are platform gaps and are out of scope
unless explicitly selected.
