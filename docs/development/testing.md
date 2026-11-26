# Testing

> **Scope**: how to test Safecor and its products — the pytest suites, the role of the emulator, the emulatable surface, the operator console, and the quality gates.
>
> **Last updated**: 2026-11-20
>
> **Code**: `python/emulator/` (the `safecor_emulator` package), `python/lib/` (the library tests).

## The test suites

| Suite | Where | How to run |
|-------|-------|-----------|
| Emulator | `python/emulator/tests/` | `cd python/emulator && PYTHONPATH=src:../lib/src python -m pytest tests/ -q` |
| Library | `python/lib/` | the project's non-regression suite (run in full before any push) |

**Test baselines** (no Python change required by documentation work): the emulator suite passes (a few pre-existing GUI failures are tracked separately); the library suite has a known flaky baseline — compare against it, do not chase single failures.

**Hardware run sheets**: the channels→vchan migration (version 2) is validated on real hardware with run sheets in `docs/plans/test-channels-migration/` (one file per run: environment, checks, findings, resolutions).

## The role of the emulator

The emulator (`python/emulator/src/safecor_emulator/`) reproduces the appliance **on a plain machine, without Xen**, by three means that all keep the `safecor` library untouched:

1. **OS/hardware fakes** (`activate.py`) — patch the module-level OS touch-points of `safecor._system` (`psutil`, `LibvirtHelper`, and `open` for sysfs/proc) and seed an in-memory `xen` bindings stub (the xenstore tree: `screen_size`/`screen_rotation`, the domid cache — ADR 0006), driven by a `SystemProfile` dict. Installed from the outside and fully reversible (`uninstall_fakes`).
2. **Mock core peers** (`peers/`) — `MockDom0Controller` and `MockSysUsbController` answer the core MQTT commands over a local broker, operating on local directories instead of real hardware.
3. **A local broker** (`broker.py`) — an external `mosquitto` on TCP 1883, so the `safecor` clients (in `TCP_DEBUG` mode) and the product under test all connect to the same bus.

The `Emulator` orchestrator brings the three together (context manager) and exposes the **scenario API** (`attach_disk`, `detach_disk`, `set_energy_state`, `power_off`/`power_on`, `set_default_language`, `restart_domain`, `inject_key`/`mouse_click`, `ping`, …). The `safecor-emulator` CLI starts it standalone; the `pytest_plugin` exposes it as a session fixture so a product's own test suite can drive the emulated core.

> **Note**: the emulator's fake of `LibvirtHelper` will become unnecessary when libvirt is removed from Dom0 (issue #265 — see [../architecture/decisions/0005-remove-libvirt-from-dom0.md](../architecture/decisions/0005-remove-libvirt-from-dom0.md)).

## The emulatable surface

Each row is a **function the platform exposes**, where its data comes from on a real system, and how the emulator currently fakes it (✅ faked, ⚠️ partial, ❌ missing, 📄 documented but not implemented). The full catalogue with the API methods and payload fields is in [../specifications/features.md](../specifications/features.md).

### Environment / identity (OS + topology)

| Function | Real source | Emulator today |
|----------|-------------|----------------|
| Product topology | `/etc/safecor/topology.json` → `System.get_topology()` | ✅ served at that path + parsed → `Environment` |
| System UUID | sysfs `/sys/class/dmi/id/product_uuid` | ✅ fake `open` |
| Screen size / rotation | xenstore `screen_size` / `screen_rotation` + fb0 | ✅ in-memory xenstore stub + fake `open` |
| CPU count / affinity | libvirt `get_cpu_count` / `get_domains` | ✅ fake `LibvirtHelper` (hard-coded Dom0 + sys-usb) |
| Memory / CPU freq / load | `psutil` | ✅ fake `psutil` |
| Boot time / uptime | `psutil.boot_time` | ✅ fake `psutil` |

### Storage & disks (provided by `sys-usb`)

| Function | Real source | Emulator today |
|----------|-------------|----------------|
| List disks | `sys-usb` → `list_disks` response | ✅ `MockSysUsb` (local dirs) |
| Disk hot-plug / unplug | `disks/state` notification | ✅ `attach_disk` / `detach_disk` (scenario API) |
| List / read / copy / create / delete files | `sys-usb` file API | ✅ `MockSysUsb` |
| File fingerprint | `FileHelper.calculate_fingerprint` (md5) | ✅ real `FileHelper` on local files |
| Mount / unmount archive | `sys-usb` `mount_file` / `unmount` | ✅ `MockSysUsb` (real `mount`) |
| Clear sys-usb queues | `sys-usb` `clear-queues` | ❌ not implemented in `MockSysUsb` |
| Disk capacity (`storage_info`) | — | 📄 documented, not implemented (platform gap) |

### System & workflow (provided by Dom0)

| Function | Real source | Emulator today |
|----------|-------------|----------------|
| System information | `system/info` response | ✅ `MockDom0` (delegates to the faked `System`) |
| Energy state | `psutil.sensors_battery` | ✅ configurable `energy_level` / `plugged` |
| Default / current language | Dom0 settings (from the topology) | ⚠️ `MockDom0` has an isolated `default_language`, not wired to the topology |
| Restart a domain | `reboot-domain.sh` | ⚠️ records + responds accepted (no real restart) |
| Shutdown | `poweroff` | ⚠️ records + responds accepted (no real poweroff) |
| GUI ready (hide splash) | Dom0 kills the splash (`feh`) | ⚠️ responds accepted (no real splash kill) |
| Switch GUI (focus) | Dom0 `XcbController` | ⚠️ responds accepted (no real X11) |
| Component discovery | Dom0 + sys-usb | ✅ both mocks |
| Ping / keepalive | `ping` response | ✅ `Emulator.ping` round-trip |
| Get my config (`my_config`) | Dom0 full topology response | ❌ not implemented in `MockDom0` |
| Monitoring | — | 📄 documented, not implemented (platform gap) |

### Logging & input

| Function | Real source | Emulator today |
|----------|-------------|----------------|
| Log levels | `Logger` → local file + `system/events/*` | ✅ real `Logger` runs; peers publish via it |
| Set log level / save log | `system/events/set_loglevel`, `save_log` | ⚠️ partial |
| Keyboard / mouse injection | `InputsDaemon` reads XenBus events | ✅ `FakeInputDevice` (XenBus wire format) |

**Known gaps** (a product exercising them would hang or get no response): `clear_sys_usb_queues`, business domains in the fake `LibvirtHelper.get_domains()`, the language settings (gated by the B1 code bug, issue #217 — see [protocol.md](protocol.md)), `my_config`.

## The operator console

The operator console is a QML window that runs the emulator **in-process**, shapes the environment from a product **`topology.json`**, and gives a human the **controls** (the scenario API) and the **observation** (live state + journals) needed to drive a product (e.g. Saphir) while manipulating the platform.

### Launching the console

```console
$ safecor-emulator --gui --topology /path/to/topology.json
```

- `--gui` opens the window (without it, the CLI stays fully headless).
- `--topology` is the product `topology.json` that defines the environment (screen, USB, languages, business domains, hardware **configurations**).
- The PySide6 dependency is optional: `pip install safecor-emulator[gui]`.

### The window

Two columns, plus a language toggle in the header:

| Region | Content |
|--------|---------|
| **Header** | **Interface** — the console's own UI language (EN/FR), switchable at runtime. |
| **Left — Setup** | Topology path, hardware **Configuration** selector, **Start** / **Stop**. |
| **Left — Controls** | Disks, Energy, Product language, Workflow, Logging, Debug. |
| **Right — State** | Live read-only view of the emulated environment. |
| **Right — Components** | The emulated business domains (peers) and their state. |
| **Right — Journals** | **Actions** timeline; **MQTT events** and **Platform log** tabs. |

A red **warning banner** appears at the top when an action cannot be applied (e.g. the emulator is not started); it auto-dismisses after 20 s.

### Setting up the environment

1. **Topology** — set the path to `topology.json` (*Browse…* or type it), then **Load**. The environment (screen, USB, languages, domains, configurations) is parsed from it.
2. **Configuration** — pick a hardware `configurations` entry, or **(standard)** for the default hardware. This sets the DMI identity so the platform applies the matching `settings` (screen size, USB, PCI, …).
3. **Start** / **Stop** — start or stop the emulated platform (broker + peers). The controls below are only enabled while running.

### The controls (left column)

| Group | What you can do |
|-------|-----------------|
| **Disks** | Attach a disk (`id` + `root path`) or detach one. Emulated disks run on local directories. |
| **Energy** | Set the battery **Level** (0–100 %), toggle **AC plugged**, **Power off** / **Power on**. |
| **Product language** | Set the emulated product's default language (from the topology's `languages`). |
| **Workflow** | **Restart** a domain; **Shutdown (W2)**, **GUI ready (W4)**, **Switch GUI (W5)** to another domain. |
| **Logging** | Set the platform log **Level**; **Save** the log to a disk; **Record journal** / **Record events** to a file path (empty path stops recording). |
| **Debug** | **Ping** a domain with arbitrary data. |

> **Note**: **Shutdown (W2) / GUI ready (W4) / Switch GUI (W5)** are **faked** in the emulated Dom0 — they record the action and respond `accepted`, with **no** real power-off, splash or X11 side effect.

### Observing (right column)

- **State** — product name, languages + default, screen (W×H + rotation), USB, business domains, energy level, broker (port / owned-or-reused), connected peers, restarted domains.
- **Components** — the emulated business domains (peers) and their running state.
- **Journals** — **Actions** (the timeline of operator-triggered scenario steps, with *Clear*); **MQTT events** / **Platform log** (the requests handled / notifications published by the mocks, and the captured platform log lines). Each journal is a scrollable list that auto-scrolls to the newest line; the **Copy** button copies the current stream to the clipboard.

### Interface language

The **Interface** combo (header) switches the console's own UI between **English** and **French** at runtime. This is independent of the **Product language** control (which sets the emulated product's language). Translations live in `i18n/{en,fr}.ts` (compiled to `.qm`) and the QML is retranslated on change via `QQmlApplicationEngine.retranslate()`. The window and its bindings are validated offscreen by `tests/test_gui.py` / `tests/test_i18n.py`.

## Quality gates

- **Never commit** before running: (1) the tests specific to the issue being worked on, (2) the project's non-regression test suite (full `pytest` run).
- **Never push** before the same two test runs, and without adding unit tests on the added code.
- **Never push** when the code coverage is under **85 %**.
- After a push, the GitHub issue must be updated (tasks and status).
