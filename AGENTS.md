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

## Coding standards

- Follow the existing naming conventions

## Issue tracking

- Every code commit must be linked to a GitHub issue. Search existing issues first; create a new one only if none fits.
- Ask the user for validation **before** creating an issue.
- One commit = one issue (atomic commits). A single issue may span multiple commits if they are tightly coupled, but the default is 1:1.
- All work that modifies existing code happens on a **dedicated branch** (never directly on `main`).
- Label every issue at creation time. Use component labels (e.g. `emulator`, `lib`, `diag`) plus a type label (`bug`, `feature`, `technical-debt`, `testing`, etc.).

## Chat rules

- Respond in the same language as the prompt's
- Never commit or push unless explicitly asked to do so

## Documentation standards

- Write documentation, comments and commits in english language even if the prompt is in another language.
- Update the documentation in /docs and the Doxygen comments of the source code up to date when applying changes.
- The Doxygen documentation must be written only in the implementation files unless the function is encoded in the header file.
- Keep `Readme.md` ("Current features") and `docs/manual.md` in sync with user-visible changes.
- Keep `README.fr.md` (French language) and `README.md` (English language) in sync together.