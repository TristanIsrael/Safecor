# Safecor Emulator — Operator Console Plan

> **Status**: **Phase 0 + 1 + 2 implemented and validated** — 51/51 emulator tests pass;
> coverage `console.py` 98 %, `events.py` 97 %, `gui.py` 97 %, `emulator.py` 85 %;
> zero new lint/type errors. **Phase 3 (CLI `--gui` + i18n) is next.**
>
> **Last updated**: 2026-11-01
>
> **Branch**: `feature-241` (off `main`) — **one issue** (#241) for the whole console
>
> **Labels**: `emulator` + `feature` + `testing`
>
> **Progress**: Phase 0 — done, committed (`44d91a3`) · Phase 1 — done, committed
> (`35a19b5`) · Phase 2 — done, pending commit · Phase 3/4/5 — not started
>
> **References**: [`docs/architecture.md`](../docs/architecture.md) (esp. §5 emulatable surface),
> [`docs/features.md`](../docs/features.md) (function catalogue),
> [`docs/doc-sync-issues.md`](../docs/doc-sync-issues.md) (code↔doc issues, incl. B1/#217),
> [`plans/emulator-context.md`](emulator-context.md) (agreed spec + validated function set)

---

## 0. Objective

Deliver a **graphical operator console** for the Safecor emulator: `safecor-emulator --gui`
opens a QML window that runs the `Emulator` in-process, is shaped by a product
**`topology.json`**, and gives a human the **controls** (scenario API) and **observation**
(live state + journals) needed to drive a Safecor-based product (e.g. Saphir) by hand while
manipulating the platform. This unblocks Saphir Phase 14 (14.2 interactive control, 14.3
observation).

**Non-goals** (this iteration):
- No external-IPC control of a separately-running emulator (in-process only).
- No scenario **replay** engine (the Actions journal is browse-only).
- No new product-side features (the console only drives/observes the platform).
- No **input-injection control** in the console (input is already transparent to the Domains;
  the operator drives the real product GUI directly). `FakeInputDevice` remains available to tests.
- No **`storage_info` / `monitoring` / `benchmark`** (documented but not implemented in the code
  — [`doc-sync-issues.md`](../docs/doc-sync-issues.md) §2).
- No fix of **B1/#217** (language list bug) here — the language control is built, its E2E
  validation is deferred to the separate #217 fix.

## 1. Architecture of the new code

```
python/emulator/src/safecor_emulator/
├── emulator.py            # (extended) Emulator: topology loading, serving, domain reflection
├── profile.py             # (kept) SystemProfile — now an override on top of the topology
├── activate.py            # (extended) install_fakes: serve /etc/safecor/topology.json;
│                                   LibvirtHelper.get_domains reflects business domains
├── topology_env.py        # (NEW) parse topology.json -> env (screen/usb/languages/product/domains)
├── events.py              # (NEW) thread-safe event bus: actions + MQTT events + platform log
├── console.py             # (NEW) Python QObject controller (QML singleton): properties,
│                                   signals, slots calling the scenario API
├── qml/                   # (NEW) QML sources
│   ├── main.qml
│   ├── OperatorWindow.qml
│   ├── qmldir
│   └── Components/        # SetupPanel, ControlPanel, StatePanel, JournalsPanel, ...
├── i18n/                  # (NEW) en.ts / fr.ts (+ compiled .qm)
├── gui.py                 # (NEW) QGuiApplication + QQmlApplicationEngine bootstrap
└── cli.py                 # (extended) --gui flag
```

**Layering**: `qml/` (views) → `console.py` (QObject: properties/signals/slots) →
`Emulator` (scenario API + state) → peers/fakes (platform). The QML never touches the
`Emulator` directly; `console.py` is the single bridge (Saphir/demo2 convention).

## 2. Phase 0 — Topology-driven environment (foundation, no GUI) — DONE (committed `44d91a3`)

**Goal**: the emulated environment is derived from a product `topology.json`, served to the
product under test, and the business domains are reflected. This is the prerequisite for the
whole console and is independently valuable + testable.

- **0.1** `topology_env.py` — load + parse a `topology.json`
  (reuse `System.get_topology_struct` / `__parse_topology` / `ConfigurationHelper.apply_configuration`
  where possible) → an `Environment` dataclass: `product_name`, `languages`, `default_language`,
  `screen {width,height,rotation,enabled,default_focus}`, `use_usb`, `business_domains[]`.
- **0.2** Serve the file: extend `install_fakes` / `_build_fake_files` so that
  `open("/etc/safecor/topology.json")` (and an override path) returns the provided file's
  content. Keep `SystemProfile` as the source of the remaining hardware keys.
- **0.3** Reflect business domains: extend the fake `LibvirtHelper.get_domains()` to return
  `Dom0` + `sys-usb` + the environment's business domains.
- **0.4** Wire `Emulator.__init__` / `start` to accept a `topology` path (or `Environment`),
  merge it with the `SystemProfile` override, and feed `MockDom0` the topology's
  `default_language` + `languages` (so `MockDom0.default_language` is no longer isolated).
- **0.5** **Configuration selector support** — expose the `configurations` entries (name →
  `identifier`) from the `topology.json`. Add an API to select one (or none): set the **DMI
  fakes** (`/sys/class/dmi/id/{sys_vendor,product_name,…}`) to the selected configuration's
  `identifier` values so `ConfigurationHelper.apply_configuration` matches it and applies its
  `settings`; « none » sets DMI that matches no configuration (→ standard values).
- **Validation**: unit tests — a Saphir-like `topology.json` produces the expected `Environment`;
  a process with the fakes installed reads back the served topology and sees the business domains;
  language defaults flow to `MockDom0`; selecting a `configurations` entry changes the applied
  screen/usb/pci accordingly, and « none » yields the standard values. Existing e2e suites still
  pass (backward compatible).

## 3. Phase 1 — Event bus + controller (Python, no QML) — DONE (pending commit)

**Goal**: a testable `console.py` `QObject` that owns the live state and the journals, and
exposes the scenario controls as slots.

- **1.1** `events.py` — a thread-safe, bounded event bus with three streams:
  - `actions` (operator-triggered scenario steps),
  - `mqtt_events` (requests handled / notifications published by the mocks),
  - `platform_log` (captured `Logger` lines).
  Each entry: timestamp, source, human-readable text, raw payload.
- **1.2** Instrument the mock peers to publish to the bus (inject the bus into
  `MockDom0Controller` / `MockSysUsbController`) — no behaviour change, only observation.
- **1.3** `console.py` — `QObject` controller:
  - **properties** (QML-visible): `running`, `brokerPort`, `brokerOwned`, `peersConnected`,
    `environment` (product/languages/screen/usb/domains), `disks`, `energyLevel`, `plugged`,
    `defaultLanguage`, `languages`, `restartedDomains`.
  - **signals**: `stateChanged`, `disksChanged`, `energyChanged`, `actionLogged`,
    `mqttEventLogged`, `logLine`.
  - **slots** (control): `start_emulator`, `stop_emulator`, `select_configuration(name|None)`,
    `attach_disk(id,path)`, `detach_disk(id)`, `set_energy(level,plugged)`, `power_off`,
    `power_on`, `set_language(code)`, `restart_domain(name)`, `shutdown()`, `gui_ready()`,
    `switch_gui(domain)`, `set_loglevel(level)`, `save_log(disk,filename)`,
    `set_record_journal(path|None)`, `set_record_events(path|None)`, `ping(target,data)`,
    `clear_actions`.
  - Slots call the in-process `Emulator` scenario API and record an `actions` entry.
- **1.4** Extend `MockDom0Controller` with **new fakes** for `shutdown` (W2), `gui_ready` (W4)
  and `switch_gui` (W5): record the action + respond `accepted` (no real poweroff / splash /
  X11 side effect). Wire them to the event bus like the other handlers.
- **Validation**: unit tests (a real started `Emulator`, or a stub) — each slot mutates the
  expected state and emits the expected signal; the new W2/W4/W5 fakes respond `accepted`; the
  bus receives action + mqtt + log entries; the two record toggles write to the user files;
  coverage ≥ 85 % on `console.py` / `events.py`.

## 4. Phase 2 — QML window (views) — **DONE** (pending commit)

**Goal**: the two-column window bound to the controller.

- **2.1** `gui.py` — `QGuiApplication` + `QQmlApplicationEngine`, register `console.py` as a
  QML singleton (demo2 pattern), load `qml/main.qml`.
- **2.2** `qml/` — `OperatorWindow.qml` (resizable, ~1100×650, `SplitView`/`RowLayout` two
  columns) and `Components/`:
  - **SetupPanel** — topology.json path + *Browse…* (`FileDialog`), **Configuration selector**
    (combo from `configurations` + « Aucune (standard) »), profile override, Start/Stop.
  - **ControlPanel** — Disks (id + path + attach/detach), Energy (slider 0–100 + AC switch +
    power off/on), Language (combo from `languages`), **Workflow** (restart name + button,
    Shutdown, GUI ready, Switch GUI), **Logging** (set_loglevel combo, save_log, two record
    toggles each with a file path), **Debug** (ping target + data).
  - **StatePanel** — live bindings: product, languages+default, screen W×H+rotation, USB,
    business domains, energy, broker (port/own-reused), peers (dom0/sys-usb), restarted domains.
  - **JournalsPanel** — Actions (timeline + *Clear*) on top; a `TabBar` with *MQTT events* and
    *Platform log* below; each a `ListView` fed by the controller signals.
- **2.3** `qmldir` + module registration so `import` works.
- **Validation**: QML loads offscreen with a fake/stub controller; bindings resolve; a
  controller-driven state change updates the expected properties (see Phase 5 for the runner).
- **Implemented**: `gui.py` (QGuiApplication + QQmlApplicationEngine; `ConsoleController`
  registered as the `safecor.emulator` / `ConsoleController` QML singleton) + `qml/`
  (`main.qml` ApplicationWindow, `OperatorWindow.qml` two-column `RowLayout`, `Components/`
  SetupPanel / ControlPanel / StatePanel / JournalsPanel + `qmldir`). `console.py` now exposes
  the environment fields (product / USB / screen / business domains / configurations) plus
  `topologyPath` and `screenWidth`/`screenHeight`, and a `load_topology` slot. Note: `QtQuick.Dialogs`
  is not installed in the target PySide6, so SetupPanel uses a path field + *Load* button (no
  `FileDialog`); the *profile override* field is deferred to Phase 3. `test_gui.py` validates
  offscreen (window loads, bindings resolve, a driven `load_topology` updates a bound item,
  `run_gui` boots in a subprocess enforcing gui.py ≥ 85 %).

## 5. Phase 3 — CLI integration + i18n

- **3.1** `cli.py` — add `--gui`: parse args, build the `Emulator` (topology + profile),
  create the `QGuiApplication` + controller + engine, run the event loop. Without `--gui`,
  the headless path is byte-for-byte unchanged.
- **3.2** i18n — `i18n/en.ts`, `i18n/fr.ts`, `QObject.tr()` in `console.py` (and QML `qsTr`
  where needed), `QTranslator` install, language selectable at runtime (mirrors the Saphir GUI).
- **Validation**: `safecor-emulator --gui` boots the window; `--help` unchanged; headless run
  still works; EN/FR strings both render.

## 6. Phase 4 — Testing + coverage gate

- **4.1** Controller unit tests (Phase 1) — real `Emulator` or stub.
- **4.2** QML offscreen tests — a subprocess **runner** (Saphir-style: `QT_QPA_PLATFORM=offscreen`,
  a fake controller injected, assert bindings / visible panels / a driven state change).
- **4.3** Topology-env tests (Phase 0).
- **4.4** Non-regression — full `pytest` of the emulator package (existing e2e suites) is green.
- **Gate**: coverage ≥ 85 % on all new modules; zero new lint/type errors (`ruff`); the full
  emulator test suite passes.

## 7. Phase 5 — Packaging + documentation

- **5.1** Packaging — include `qml/`, `i18n/*.qm` in the wheel (hatch `force-include`);
  the `gui` extra (PySide6) already exists. Confirm `safecor-emulator --gui` works from the
  installed package.
- **5.2** Documentation — update `docs/` (this architecture doc §6 + a short operator guide),
  `README.md` / `README.fr.md` ("Current features"), and Doxygen comments in the new modules.
- **5.3** Doxygen — docstrings on `topology_env.py`, `events.py`, `console.py`, `gui.py`.

## 8. Validated scope — function set + interaction model

The function set and interaction model were **reviewed bundle-by-bundle with the operator and
validated on 2026-11-01**. The authoritative table is
[`emulator-context.md`](emulator-context.md) §5 (bundles A–H: user / system / platform).
Summary of the scope decisions:

- **All bundles A–H in scope** (topology+config, disks, energy, language, workflow,
  system/components, logging, debug).
- **A**: configuration selector (combo from `configurations` + « Aucune ») drives the DMI fakes.
- **E**: `shutdown` / `gui_ready` / `switch_gui` are **faked** in `MockDom0` (new handlers).
- **G**: platform log auto-written to the system temp dir; **two separate** user-file record
  options (journal / events); set_loglevel + save_log controls.
- **H**: **ping only** — no input-injection control (input is transparent to the Domains).
- **Out of scope**: `storage_info` (S13), `monitoring` (W6), `benchmark` (D3) (not implemented in
  the code); B1/#217 fix (deferred, dependency only).

## 9. Sequencing & issue

- **Single issue** (per the agreed split), atomic commits per phase.
- Suggested order: **Phase 0 → 1 → 2 → 3 → 4 → 5** (Phase 0 first because everything depends on
  the topology-driven environment; Phases 2 and 3 can partly overlap).
- Each commit linked to the issue; branch dedicated; Kanban status advanced per the Safecor
  project conventions (Ready → In progress → In review).

## 10. Risks / mitigations

| Risk | Mitigation |
|------|-----------|
| Serving `topology.json` via fake `open` clashes with real reads | The fake only intercepts the exact topology path; all other `open` calls pass through |
| Reflecting business domains changes `get_domains` output for existing tests | Keep `Dom0`+`sys-usb` as the base; append business domains only when a topology is loaded; e2e suites use a default (no-business-domain) topology → unchanged |
| QML offscreen testing fragility | Reuse the proven Saphir subprocess-runner pattern; keep the controller 100 % Python-tested so QML tests are thin |
| Threading (peers on MQTT threads emitting to the Qt bus) | The event bus is thread-safe and Qt-signals are queued across threads |
| Backward compatibility of the headless CLI | `--gui` is opt-in; the default path is untouched and covered by the existing e2e suites |
| DMI/config selector: wrong DMI values could accidentally match an unintended configuration | « Aucune » uses DMI values guaranteed to match no `configurations` identifier; tests assert the applied settings for both a selected and a none configuration |
| W2/W4/W5 fakes might mask real behaviour | They only record + respond `accepted` (no real side effect); clearly documented as fakes, so a product cannot rely on a real poweroff/splash/X11 effect |
| Language feature partially unverifiable (B1/#217 deferred) | The control + `set`/`current`/`default` paths are tested; the **list** path is marked xfail/pending until #217 is fixed, so it is not silently green |
