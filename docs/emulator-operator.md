# Safecor Emulator — Operator Console Guide

> **Audience**: the **operator** who drives a Safecor-based product by hand on an emulated
> platform (no appliance, no Xen).
>
> **Companion docs**: [`architecture.md`](architecture.md) §6 (how the emulator fits),
> [`features.md`](features.md) (what the platform exposes), [`plans/emulator-plan.md`](../plans/emulator-plan.md).

The operator console is a QML window that runs the emulator **in-process**, shapes the
environment from a product **`topology.json`**, and gives a human the **controls** (the
scenario API) and the **observation** (live state + journals) needed to drive a product
(e.g. Saphir) while manipulating the platform.

## 1. Launching the console

```console
$ safecor-emulator --gui --topology /path/to/topology.json
```

- `--gui` opens the window (without it, the CLI stays fully headless).
- `--topology` is the product `topology.json` that defines the environment (screen, USB,
  languages, business domains, hardware **configurations**).
- The PySide6 dependency is optional: `pip install safecor-emulator[gui]`.

## 2. The window

Two columns, plus a language toggle in the header:

| Region | Content |
|--------|---------|
| **Header** | **Interface** — the console's own UI language (EN/FR), switchable at runtime. |
| **Left — Setup** | Topology path, hardware **Configuration** selector, **Start** / **Stop**. |
| **Left — Controls** | Disks, Energy, Product language, Workflow, Logging, Debug. |
| **Right — State** | Live read-only view of the emulated environment. |
| **Right — Components** | The emulated business domains (peers) and their state. |
| **Right — Journals** | **Actions** timeline; **MQTT events** and **Platform log** tabs. |

A red **warning banner** appears at the top when an action cannot be applied (e.g. the
emulator is not started); it auto-dismisses after 20 s.

## 3. Setting up the environment

1. **Topology** — set the path to `topology.json` (*Browse…* or type it), then **Load**.
   The environment (screen, USB, languages, domains, configurations) is parsed from it.
2. **Configuration** — pick a hardware `configurations` entry, or **(standard)** for the
   default hardware. This sets the DMI identity so the platform applies the matching
   `settings` (screen size, USB, PCI, …).
3. **Start** / **Stop** — start or stop the emulated platform (broker + peers). The
   controls below are only enabled while running.

## 4. The controls (left column)

| Group | What you can do |
|-------|-----------------|
| **Disks** | Attach a disk (`id` + `root path`) or detach one. Emulated disks run on local directories. |
| **Energy** | Set the battery **Level** (0–100 %), toggle **AC plugged**, **Power off** / **Power on**. |
| **Product language** | Set the emulated product's default language (from the topology's `languages`). |
| **Workflow** | **Restart** a domain; **Shutdown (W2)**, **GUI ready (W4)**, **Switch GUI (W5)** to another domain. |
| **Logging** | Set the platform log **Level**; **Save** the log to a disk; **Record journal** / **Record events** to a file path (empty path stops recording). |
| **Debug** | **Ping** a domain with arbitrary data. |

> **Note**: **Shutdown (W2) / GUI ready (W4) / Switch GUI (W5)** are **faked** in the
> emulated Dom0 — they record the action and respond `accepted`, with **no** real power-off,
> splash or X11 side effect.

## 5. Observing (right column)

- **State** — product name, languages + default, screen (W×H + rotation), USB, business
  domains, energy level, broker (port / owned-or-reused), connected peers, restarted domains.
- **Components** — the emulated business domains (peers) and their running state.
- **Journals** —
  - **Actions**: the timeline of operator-triggered scenario steps (with *Clear*).
  - **MQTT events** / **Platform log**: tabs of the requests handled / notifications
    published by the mocks, and the captured platform log lines.

  Each journal is a **scrollable** list that auto-scrolls to the newest line; the **Copy**
  button copies the current stream to the clipboard.

## 6. Interface language

The **Interface** combo (header) switches the console's own UI between **English** and
**French** at runtime. This is independent of the **Product language** control (which sets
the emulated product's language). Translations live in `i18n/{en,fr}.ts` (compiled to `.qm`).
