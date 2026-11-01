# Safecor Emulator — Session Context

> **Last update**: 2026-11-01
>
> **Session status**: specification phase — the graphical operator console is specified but **not yet implemented**
>
> **Related plan**: [`plans/emulator-plan.md`](emulator-plan.md)
>
> **Related architecture**: [`docs/architecture.md`](../docs/architecture.md)

---

## 1. Why this work exists

The **Saphir** product (a sheep-dip on Safecor) is blocked on **Phase 14** of its
refactoring plan: a *semi-automated validation environment*. A human tester must be able to
drive the **real Saphir GUI** (mouse/keyboard) while, in parallel, **manipulating the Safecor
emulator** to trigger platform events (attach/detach storage, power state, language, domain
restart…) and **observing** both the platform and the application's internal state.

The Safecor emulator today is a **headless test tool**: it exposes a programmatic *scenario
API* (`attach_disk()`, `set_energy_state()`, …) used by the pytest integration suites, but it
has **no human-facing control surface** and **no live observation** of the system under test.

This work delivers that missing surface: a **graphical operator console** for the emulator.

## 2. What the emulator provides today

| Component | File | Role |
|-----------|------|------|
| `Emulator` | `emulator.py` | Orchestrator: broker + fakes + mock peers. Context manager. Exposes the **scenario API** |
| `SystemProfile` / `load_profile` | `profile.py` | Flat dict of hardware/OS characteristics driving the fakes (uuid, cpu, screen, mem, …) |
| `install_fakes` / `uninstall_fakes` | `activate.py` | Patches `safecor._system` from the **outside** (psutil, LibvirtHelper, `xenstore-read`, sysfs `open`) |
| `MosquittoBroker` | `broker.py` | Manages an external `mosquitto` on TCP 1883 (reused if already listening) |
| `MockDom0Controller` | `peers/mock_dom0.py` | Answers Dom0 MQTT commands (system info, energy, language, restart, delete) on a local dir |
| `MockSysUsbController` | `peers/mock_sys_usb.py` | Answers USB/disk MQTT commands (list/read/copy/create files, mount) on local dirs |
| `FakeInputDevice` | `fake_input.py` | Produces XenBus wire-format keyboard/mouse events for input injection |
| `safecor-emulator` | `cli.py` | CLI entry point: starts the emulator and **sleeps** (no interactive control) |
| `pytest_plugin` | `pytest_plugin.py` | Session-scoped `emulator` fixture for product test suites |

**Scenario API available today** (on `Emulator`):
`attach_disk` / `detach_disk`, `set_energy_state` / `power_off` / `power_on`,
`restart_domain` (+ `restarted_domains`), `set_default_language`,
`inject_key` / `press_key` / `release_key` / `click` / `mouse_move` / `mouse_click`.

**Test baseline**: the emulator e2e suites (`tests/test_emulator.py`, `tests/test_features.py`)
run against a real local `mosquitto` and drive Safecor + a product over MQTT.

## 3. The agreed specification (from the 2026-11-01 design session)

### 3.1 Form factor
- **In-process**: `safecor-emulator --gui` starts the **QML window and the `Emulator` in the
  same process**. Without the flag, the headless behaviour is unchanged (backward compatible).
- **PySide6 + QML**, following the repo convention (pattern `demo2`: `qml/` directory + a
  Python `QObject` controller registered as a QML singleton).
- **Bilingual EN/FR** (the GUI is a product-adjacent tool, like the Saphir GUI).
- **Resizable window**, default ~1100×650, two-column layout with an adjustable splitter.

### 3.2 Environment input — `topology.json` is primary (key decision)
On a real system the environment comes from `/etc/safecor/topology.json`
(`System.get_topology()` → `get_topology_struct` → `__parse_topology` →
`ConfigurationHelper.apply_configuration`). **Today the emulator's fake `open` does not serve
`topology.json`**, so a product under test cannot see the intended topology.

The console must:
1. **Take a `topology.json` file** as the primary environment input (path field + file dialog).
2. **Serve it at `/etc/safecor/topology.json`** through the fake `open`, so a running product's
   `System.get_topology()` returns exactly the topology shown in the console.
3. **Parse it** to derive the emulated environment: product name, `languages` +
   `default_language`, screen (size/rotation), USB on/off, and the **business domains**
   (e.g. `saphir-gui`, `saphir-av-clamav`, `saphir-av-eset`).
4. The flat **`SystemProfile` remains an override** for hardware characteristics not defined by
   the topology (uuid, CPU count, RAM, frequencies, DMI keys). This keeps the existing 530 GUI
   tests and the e2e suites working.
5. The fake **`LibvirtHelper.get_domains()`** reflects `Dom0` + `sys-usb` + the topology's
   business domains, so the product's `get_topology().domains` matches the console.
6. **Configuration selector**: the operator picks one of the `configurations` entries defined in
   the `topology.json` (or « Aucune (standard) »). The choice drives the **DMI fakes**
   (`/sys/class/dmi/id/…`) so that `ConfigurationHelper.apply_configuration` matches the selected
   configuration and applies its `settings` (usb/screen/pci); « Aucune » sets DMI that matches no
   configuration → standard topology values.

### 3.3 Window layout (two columns)
- **Left column**
  - **Setup**: `topology.json` path (+ browse), **configuration selector** (combo from
    `configurations` + « Aucune (standard) »), profile override, **Start / Stop** the emulator.
  - **Control**:
    - *Disks*: id + path, **attach / detach** (hot-plug/unplug, publishes `DISK_STATE`).
    - *Energy*: battery level slider (0–100) + AC-plug switch, **power off / power on**.
    - *Language*: combo populated from the topology's `product.languages`.
    - *Workflow*: **restart domain** (name + button), **Shutdown**, **GUI ready**, **Switch GUI**
      (domain).
    - *Logging*: **set_loglevel** (combo), **save_log** (disk + filename), and **two separate
      record toggles** — « record journal » and « record events » — each to a user-specified file.
    - *Debug*: **ping** (target domain + data).
  - **State (live)**: product name, languages + default, screen W×H+rotation, USB on/off,
    business domains, energy (level + plugged), broker (port, own/reused), peers
    (dom0 / sys-usb connection state), restarted domains.
- **Right column** — **Journals** (stacked):
  - **Actions**: timestamped timeline of the scenario played (browse + **Clear** button).
  - **Tabs**:
    - *MQTT events* — requests handled by the mocks + notifications published
      (timestamp, topic, payload summary).
    - *Platform log* — the `safecor` `Logger` lines emitted by the platform.

### 3.4 Interaction model
- Controls call the existing **scenario API** on the in-process `Emulator`.
- The **Actions** journal records every action the operator triggers (the replayable scenario).
- The **MQTT events** journal is fed by the mock peers (what the platform sees from the product).
- The **Platform log** journal is fed by capturing the `Logger` output.

## 4. Key design decisions (validated)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Process model | In-process (window + emulator in one process) |
| 2 | Environment source | `topology.json` primary, `SystemProfile` as hardware override |
| 3 | Topology visibility | Serve `topology.json` to the product via fake `open` |
| 4 | Business domains | Reflected in fake `LibvirtHelper.get_domains()` |
| 5 | Journal content | Actions (scenario) + Safecor logs split into two tabs (MQTT events / platform log) |
| 6 | Actions journal | Browse-only (no replay engine) |
| 7 | GUI language | Bilingual EN/FR |
| 8 | Layout | Two columns: control+state \| journals |
| 9 | GUI stack | PySide6 + QML (repo convention, like demo2) |
| 10 | Window | Resizable, default ~1100×650 |
| 11 | Testing | Controller unit tests + QML offscreen (subprocess runner, Saphir-style); ≥ 85 % coverage on new code |
| 12 | Issue split | A **single** issue for the whole console |
| 13 | Configuration selector | The operator selects a `configurations` entry from `topology.json` (or none → standard); the choice drives the DMI fakes so `apply_configuration` matches it |
| 14 | Workflow fakes | W2 shutdown / W4 gui_ready / W5 switch_gui are **faked** in `MockDom0` (record + respond accepted) |
| 15 | Log recording | Platform log auto-written to the system temp dir; **two separate** user-file record options (journal / events) |
| 16 | Input | No input-injection control (input is transparent to the Domains); `FakeInputDevice` remains available to tests |
| 17 | Language bug | B1/#217 deferred — the language control is built; its E2E validation waits for the separate fix |

## 5. Function set & interaction model (validated — 2026-11-01)

All bundles (A–H) of [`docs/features.md`](../docs/features.md) are **in scope**, with the
per-bundle interaction model below (user / system / platform). This is the validated contract
for the implementation.

| Bundle | Functions | User (control / observe) | System (fake) | Platform (topic / peer) |
|--------|-----------|--------------------------|----------------|--------------------------|
| **A. Topology / env** | T1, T2–T6, business domains | **Control**: `topology.json` path + *Browse…*, **configuration selector** (combo from `configurations` keys + « Aucune (standard) »), profile override (JSON), Start/Stop. **Observe**: product name, languages+default, screen W×H+rotation, USB, business domains, CPU/mem, broker, peers | fake `open` serves `/etc/safecor/topology.json`; **DMI fakes** driven by the selected configuration's `identifier` (so `apply_configuration` matches it) or match none for « Aucune »; `psutil`/`LibvirtHelper` fakes from `SystemProfile`; business domains in `LibvirtHelper.get_domains()` | none (environment; feeds `System.get_topology()`) |
| **B. Storage / disks** | S2–S11 | **Control**: disk id + path + *Browse…*, Attach/Detach. **Observe**: live disk list; file ops in MQTT journal | `MockSysUsb` on local dirs; `DISK_STATE` notif on attach/detach | `disks/*` via `MockSysUsb` |
| **C. Energy** | E1 | **Control**: battery slider (0–100) + AC-plug switch + Power off/on. **Observe**: level + plugged | `MockDom0.energy_level` / `.plugged` | `energy/state` via `MockDom0` |
| **D. Languages** | L1–L5 | **Control**: language combo (from `product.languages`). **Observe**: default + current | `MockDom0` language **wired to the topology** + `System().set_setting/get_setting` | `settings/languages/*` + `settings/changed` via `MockDom0` |
| **E. Workflow** | W2, W3, W4, W5 | **Control**: restart domain (name + button); **Shutdown**, **GUI ready**, **Switch GUI** (domain). **Observe**: restarted list | `MockDom0.record_restart`; **NEW fakes** for shutdown / gui_ready / switch_gui added to `MockDom0` | `workflow/restart_domain`, `workflow/shutdown`, `workflow/gui_ready`, `gui/switch` via `MockDom0` |
| **F. System / components** | W1, C1 | **Observe only**: state panel + discovery journal | `MockDom0` (system info) + `MockDom0`/`MockSysUsb` (discovery) | `system/info`, `discover/components` |
| **G. Logging** | G1, G2, G3 | **Control**: set_loglevel (combo), save_log (disk+filename); **two separate record toggles** — « record journal » (actions) and « record events » (MQTT), each to a **user-specified file**. **Observe**: Platform log journal. Platform log file written **automatically to the system temp dir** | capture `Logger` output; local log redirected to system temp dir | `system/events/*`, `set_loglevel`, `save_log` |
| **H. Debug / input** | D1 | **Control**: ping (target domain + data). **Observe**: ping in MQTT journal. **No input-injection control** (input is already transparent to the Domains — the operator drives the real product GUI directly) | `MockDom0`/`MockSysUsb` answer ping | `debugging/ping/<target>` |

### Decisions & scope notes
- **B1 / #217 (language list bug)**: the language **control** is implemented in the console, but
  the end-to-end validation of the list-languages path is **deferred** until #217 is fixed
  separately. Documented as a dependency, not a blocker for the other bundles.
- **W2/W4/W5 (shutdown, gui_ready, switch_gui)**: **in scope** — new fakes added to
  `MockDom0` (record + respond accepted; no real poweroff/splash/X11 side effect).
- **Not emulated** (out of scope): `storage_info` (S13), `monitoring` (W6), `benchmark` (D3) —
  documented but not implemented in the code at all ([`doc-sync-issues.md`](../docs/doc-sync-issues.md) §2);
  input injection (I1) as a console control (transparent to Domains).
- **Platform log capture** is platform-only (not the product's own log lines).

## 6. References

- Saphir Phase 14 (the consumer of this work): `Saphir/docs/plans/refactoring-plan.md` §"Phase 14".
- Safecor core library: `python/lib/src/safecor/`.
- Emulator package: `python/emulator/src/safecor_emulator/`.
- QML controller convention: `python/demo2/src/demo2/` (`main.py`, `AppController.py`, `qml/`).
