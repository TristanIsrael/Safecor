# Project rules

## Architecture

Safecor is a software architecture for building security products (kiosk/embedded style) on Alpine Linux + Xen.

- A privileged management domain (**Dom0**) runs the `safecor` library (control, repository, supervision).
- Business applications run in virtual machines (**DomU**). Core DomUs include `sys-usb`.
- Domains communicate with **MQTT** (paho-mqtt) transported over **UNIX socket (Dom0)** or **serial port (DomU)**. Payloads are JSON (msgpack also available).
- The product topology (domains, vCPU groups/pinning, screen, USB, PCI blacklist, configurations) is defined in `/etc/safecor/topology.json` and parsed into a `Topology` object.
- Hardware requires VT-x (virtualization) and VT-d/IOMMU.
- Many `System` functions must run in Dom0 or in DomU depending on the call — check the docstrings.
- x86_64 only; tested on Alpine 3.20/3.21.

### Directory layout

| Folder | Description |
|---|---|
| `python/lib` | Core Python package `safecor` (src layout, hatchling/poetry) |
| `python/demo2` | Demo product app (PySide6 + QML) |
| `python/emulator` | `safecor-emulator`: hardware-free test/emulation infra for Safecor and products |
| `python/diag` | Bootable diagnostic app (checks VT-x/VT-d compatibility), shipped as USB ISO |
| `setup/packages` | Alpine .apk package sources |
| `setup/iso` | ISO/bootable image generation scripts |
| `setup/docker`, `setup/infrastructure` | Local dev (Docker) and deployment (Ansible) |
| `certs` | Public key of the Alpine repository |
| `misc` | Fonts, logos, scripts |

### Core library classes (`python/lib/src/safecor/`)

- `Api` / `ApiHelper` — high-level API used by DomU apps.
- `Dom0Controller` — handles Dom0-side MQTT commands: file repository (list/read/copy/delete/fingerprint), shutdown, restart domain, system info, energy state, component discovery, ping, settings/language, GUI switch.
- `System` (singleton) / `Topology` / `Domain` — system state, screen size/rotation, UUID, CPU allocation and pinning per vCPU groups, settings from kernel cmdline, inotify file monitoring.
- `MqttClient`, `SerialMQTTClient`, `MqttFactory`, `MqttHelper`, `Topics` — MQTT client/transports and topic definitions (topics use a `group/verb` structure, e.g. `system/disks/list_files/request`).
- `XenStore`, `LibvirtHelper` — Xen xenstore and libvirt integration (screen size/rotation read from xenstore).
- `XcbController` — X11/XCB GUI control (optional import).
- `DiskMonitor`, `FileHelper` — disk/filesystem monitoring.
- `SysUsbController` — USB passthrough management. (The `MockSysUsbController` used for testing now lives in the `safecor_emulator` package.)
- `Logger` / `SysLogger` — logging, events published over MQTT topics (`system/events/*`).
- `RequestFactory`, `ResponseFactory`, `NotificationFactory` — protocol message builders.
- `TaskRunner`, `InputsDaemon`, `Mouse`, `KeymapFR` — background tasks and input handling.
- `Constants`, `Settings`, `ConfigurationHelper` — constants and configuration handling.
- `deprecated/` — legacy code, do not extend.

### Tech stack

- Python 3.9+ (3.11 for development), Alpine Linux, Xen, libvirt.
- MQTT (paho-mqtt >= 2.0), pyserial, pyudev, msgpack, joblib, humanize, psutil, inotify.
- GUI: PySide6 (Qt6) + QML for demo2/diag apps.
- Packaging: hatchling + poetry, signed Alpine apk repository, ISO images.
- Docs: Sphinx (autodoc + RTD theme), published on GitHub Pages; CI via GitHub Actions (`build-all.yml`, `documentation.yml`).
- License: proprietary and restrictive (no fork/copy/reuse without written permission).

## Documentation

The following documents **must** be read during design, planning and coding:
- `docs/features` - The list of features and NFR
- `docs/architecture.md` - The architecture of the product
- The Safecor Wiki project available locally in the folder `safecor.wiki` or on Github.

## Installation packages

- Safecor components are packaged into Alpine Linux packages (APK).
- The Alpine Linux packages definitions are in `setup/packages/safecor`.
  - `setup/packages/safecor/safecor-container-debian` is the package that installs a Debian LXC container in a Domain of a Safecor system.
  - `setup/packages/safecor/safecor-core` is the package that contains the Dom0 core controller and the scripts that setup the core of Safecor.
  - `setup/packages/safecor/safecor-diag` is a package that setup the diagnostic app on a platform. It does not contain Safecor.
  - `setup/packages/safecor/safecor-domu-base` is a package that prepares a Domain to be integrated into a Safecor system. 
  - `setup/packages/safecor/safecor-gui-base` is a package that prepares a Domain to be integrated into a Safecor system as graphical user interface (GUI). 
  - `setup/packages/safecor/safecor-hardening` is a package that hardens a Domain in a Safecor system. 
  - `setup/packages/safecor/safecor-lib` is a dependency package that installs the Safecor python library. 
  - `setup/packages/safecor/safecor-splash` is the package that setup the splash screen of a Safecor vanilla system. 
  - `setup/packages/safecor/safecor-sys-usb` is the package installed in the sys-usb Domain of a Safecor system. 
  - `setup/packages/safecor/safecor-syslog` is the package that connects a Domain to the Safecor logging facility using `syslog`. 
  - `setup/packages/safecor/safecor-tests` is a testing Safecor appliance. 
  - `setup/packages/safecor/safecor-tests-gui` is the package that setup the graphical user interface (GUI) of the test appliance. 

## Build

- Versioning rule (scheme `MAJOR.MINOR.PATCH`, e.g. `2.2.0`):
  - A bug fix bumps the last digit (patch) only.
  - A new feature bumps the second digit (minor) and resets the last digit to 0.
  - The first digit (major) is bumped only by the product maintainer.
- When the components versions are modified, the Alpine Linux packages must be updated to reflect the components versions.

## Coding standards

- Follow the existing naming conventions. The codebase is the reference; when in doubt, match the surrounding code.
- Use `ruff` format to format Python code consistently.
- Do not introduce unrelated formatting changes.

Naming conventions:

| Domain | Convention | Examples |
|---|---|---|
| Python — classes | `PascalCase` | `ApplicationController`, `EMAETAEstimator` |
| Python — methods / variables | `snake_case` | `start_transfer`, `remaining_time` |
| Python — private methods | double-underscore (name mangling) | `__set_system_state`, `__handle_disk_state` |
| Python — constants | `UPPER_SNAKE` | `ANTIVIRUS_NEEDED`, `TOPIC_ANALYSIS`, `DEVMODE` |
| Python — enums | `PascalCase` (no underscores) | `SystemAnalysisRunning`, `FileClean` |
| QML — components | `PascalCase` | `AnalysisPanel`, `FilesSelectionPanel` |
| QML — properties / bindings | `camelCase` | `systemState`, `queueSize`, `nbClean` |
| MQTT topics | `saphir/analysis/{request,response,status,error,stop,resume,reset}`; `system/...` | — |

- Comments, documentation and commits are in **English** (see *Documentation standards*).

## Linting and static analysis

- Use `ruff` check to detect linting issues, potential bugs, and violations of coding conventions.
- Run static analysis on all modified Python files, included newly added files.
- Do not suppress linting rules unless there is a clear justification.
- Use type checking and resolve any new type errors introduced by the changes.

## Issue tracking

- Every code commit must be linked to a GitHub issue. Search existing issues first; create a new one only if none fits.
- Ask the user for validation **before** creating an issue.
- One commit = one issue (atomic commits). A single issue may span multiple commits if they are tightly coupled, but the default is 1:1.
- All work that modifies existing code happens on a **dedicated branch** (never directly on `main`).
- Label every issue at creation time. Use component labels (e.g. `emulator`, `lib`, `diag`) plus a type label (`bug`, `feature`, `technical-debt`, `testing`, etc.).
- Every issue must be added to the **"Safecor Kanban"** project.
- The text of the commits and comments must be in english.
- The issue's project status must reflect the actual state of the work:
  | Status | Meaning |
  |---|---|
  | **Backlog** | The issue is mentioned but needs refinement before it can be worked on. |
  | **Ready** | The issue is fully specified and ready to be worked on. |
  | **Not ready** | The issue has an unresolved dependency (another issue, external block). |
  | **In progress** | Work is actively being done on this issue. |
  | **In review** | Implementation and tests are complete; awaiting validation. |
- **Never commit** before running:
  1. The tests specific to the issue being worked on.
  2. The project's non-regression test suite (full `pytest` run).

## Quality gates
- **Never commit** before verifying the respect of the coding standards on the added code.
- Run formatting checks before committing changes.
- Resolve all linting errors before committing changes.
- **Never push** before running:
  1. The tests specific to the issue being worked on.
  2. The project's non-regression test suite (full `pytest` run).
- **Never push** without adding unit tests on the added code.
- **Never push** when the code coverage is under 85%.
- After push, the Github issue must be updated (task and status).
- **Never commit** before updating the documentation and the plans if needed.

## Chat rules

- Respond in the same language as the prompt's
- Never commit or push unless explicitly asked to do so

## Documentation standards

- The public documentation lies in the Safecor Wiki repository
- The project's documentation lies in the /docs directory
- Write documentation, comments and commits in english language even if the prompt is in another language.
- Update the documentation in /docs and the Doxygen comments of the source code up to date when applying changes.
- The Doxygen documentation must be written only in the implementation files unless the function is encoded in the header file.
- Keep `Readme.md` ("Current features") and `docs/manual.md` in sync with user-visible changes.
- Keep `README.fr.md` (French language) and `README.md` (English language) in sync together.