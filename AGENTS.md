# Project rules

## Architecture

Safecor is a software architecture for building security products (kiosk/embedded style) on Alpine Linux + Xen.

- A privileged management domain (**Dom0**) runs the `safecor` library (control, repository, supervision).
- Business applications run in virtual machines (**DomU**). Core DomUs include `sys-usb`.
- Domains communicate with **MQTT** (paho-mqtt): over the **UNIX socket** on Dom0, over the **vchan `msg` channel** on the DomUs (each DomU runs a local broker bridged to Dom0). Payloads are JSON (msgpack also available).
- The product topology (domains, vCPU groups/pinning, screen, USB, PCI blacklist, configurations) is defined in `/etc/safecor/topology.json` and parsed into a `Topology` object.
- Hardware requires VT-x (virtualization) and VT-d/IOMMU.
- Many `System` functions must run in Dom0 or in DomU depending on the call — check the docstrings.
- x86_64 only; tested on Alpine 3.20/3.24.

**The architecture reference is `docs/architecture/`**: start with [docs/architecture/overview.md](docs/architecture/overview.md), then the per-component files (`components/`) and the ADR registry (`decisions/`). The core library module map is in [docs/specifications/python-api.md](docs/specifications/python-api.md). The Safecor Wiki (`safecor.wiki/`) is the public documentation for human beings.

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
| `docs` | The project documentation for AI coding agents (see below) |

### Tech stack

- Python 3.9+ (3.11 for development), Alpine Linux, Xen.
- MQTT (paho-mqtt >= 2.0), pyudev, msgpack, psutil, inotify; PySide6 (Qt6) + QML for the GUI apps.
- Packaging: hatchling + poetry, signed Alpine apk repository, ISO images.
- Docs: Sphinx (autodoc), published on GitHub Pages; CI via GitHub Actions (`build-all.yml`, `documentation.yml`).
- License: proprietary and restrictive (no fork/copy/reuse without written permission).

## Documentation

The project documentation lies in `docs/`, organized as short, specialized documents for **offline** AI coding agents (duplication with the Wiki is allowed and expected):

| Path | Content |
|---|---|
| `docs/architecture/` | The architecture: `overview.md`, `configuration-management.md`, `design-rules.md`, `components/` (one file per component), `decisions/` (the ADR registry) |
| `docs/specifications/` | `features.md` (function catalogue + NFR), `topology.md`, `python-api.md` |
| `docs/development/` | `building.md`, `coding-rules.md`, `testing.md` (emulator + operator console), `protocol.md` (the MQTT contract), `packaging.md` |
| `docs/security/security-model.md` | The security design policy |
| `docs/project-status.md` | The current status of the project |
| `docs/diagrams/` | The mermaid sources (`*.mmd`) and the render theme |
| `docs/plans/` | Working plans (not reference documentation) |

The following documents **must** be read during design, planning and coding:
- `docs/specifications/features.md` — the list of features and NFR
- `docs/architecture/overview.md` — the architecture of the product
- The Safecor Wiki project available locally in the folder `safecor.wiki` or on Github.

### Diagram sync rule

The mermaid sources are `docs/diagrams/*.mmd`; the **inline** mermaid blocks in `docs/` must stay identical to them. When a diagram changes:

1. Edit the `.mmd` source **and** the inline block in the document.
2. Render: `cd docs/diagrams && mmdc -i <name>.mmd -o preview/<name>.png -c theme.json -b fdfdfd -s 2` (and without `-s 2` for the `.svg`). The previews are gitignored (local only).
3. Copy the rendered PNG and SVG to the Safecor Wiki as `images/safecor-architecture-<name>.png` / `.svg` and commit them there (the Wiki is the place where the rendered images live).

### Graphical design

The graphical design of Safecor (colors, font) is described in the page [Graphical Design on the wiki](https://github.com/TristanIsrael/Safecor/wiki/Graphical-design).

## Installation packages

- Safecor components are packaged into Alpine Linux packages (APK), defined in `setup/packages/safecor/`.
- The full package list and the product packaging rules are in [docs/development/packaging.md](docs/development/packaging.md).

## Build

- Versioning rule (scheme `MAJOR.MINOR.PATCH`, e.g. `2.2.0`): a bug fix bumps the last digit (patch) only; a new feature bumps the second digit (minor) and resets the last digit to 0; the first digit (major) is bumped only by the product maintainer.
- When the components versions are modified, the Alpine Linux packages must be updated to reflect the components versions.
- Recalculate the `sha512` APKBUILD checksums for every modified/packaged file.
- When creating an `openrc` `.initd` file, do not write python code inside the script: write a python file instead and call it from the `initd` script.
- Full reference: [docs/development/building.md](docs/development/building.md).

## Coding standards

- Follow [docs/development/coding-rules.md](docs/development/coding-rules.md): `ruff format` + `ruff check`, the naming conventions, no unrelated formatting changes.
- The codebase is the reference; when in doubt, match the surrounding code.
- Comments, documentation and commits are in **English**.

## Security rules

- The `openrc` `.initd` scripts must execute commands with a regular user (`svc-*`) and not root. If no user matches the script's subject, create a new one in the `post-install` script of the package.
- **Always reduce attack surface** (design rule #10) — see [docs/security/security-model.md](docs/security/security-model.md) and the ADRs in [docs/architecture/decisions/](docs/architecture/decisions/README.md).

## Linting and static analysis

- Use `ruff` check to detect linting issues, potential bugs, and violations of coding conventions.
- Run static analysis on all modified Python files, including newly added files.
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
- Compute the checksums of the Alpine packages before pushing if their resources have been modified.
- Never commit or push unless explicitly asked to do so
- **Never push** before recalculating the checksums of the APKBUILD files if modified.

## Chat rules

- Respond in the same language as the prompt's

## Documentation standards

- The public documentation lies in the Safecor Wiki repository (for human beings).
- The project's documentation lies in the `docs/` directory: offline technical documentation for AI coding agents.
- Write documentation, comments and commits in english language even if the prompt is in another language.
- Update the documentation in `docs/` and the Doxygen comments of the source code up to date when applying changes.
- The Doxygen documentation must be written only in the implementation files unless the function is encoded in the header file.
- Keep `README.md` ("Current features") in sync with user-visible changes.
- Keep `README.fr.md` (French language) and `README.md` (English language) in sync together.
