# Safecor Emulator

The Safecor Emulator reproduces the Safecor appliance **on a plain machine, without Xen or
real hardware**, so that a Safecor-based product (e.g. Saphir) can be developed, tested and
driven by hand. It is made of two complementary pieces:

- **A headless emulated core** — a local MQTT broker + mock `Dom0` + mock `sys-usb` that
  answer the platform commands, operating on local directories instead of real hardware.
- **A graphical operator console** (QML, EN/FR) — a window that runs the emulated core
  **in-process**, shapes the environment from a product `topology.json`, and gives a human
  the **controls** (the scenario API) and the **observation** (live state + journals) needed
  to drive a product while manipulating the platform.

> ⚠️ **Notice**
>
> The graphical console needs the optional **`gui`** extra (PySide6). The headless core does
> not.

## Installation

```console
$ pip install safecor-emulator            # headless core
$ pip install 'safecor-emulator[gui]'     # + the graphical operator console
```

## Headless core

Start the emulated core in one terminal; it keeps running so a product can be launched in
another terminal against it. Use `--profile` / `--disk` / `--storage` / `--destination` to
shape the emulated system:

```console
$ safecor-emulator --disk usb0=/path/to/files
```

Press **Ctrl+C** to stop the emulator. The `pytest_plugin` also exposes the emulator as a
session fixture, so a product's own test suite can drive the emulated core.

## Operator console

Open the graphical console:

```console
$ safecor-emulator --gui
$ safecor-emulator --gui --topology /path/to/topology.json
```

- `--topology` is optional: without it the console starts on the standard environment and a
  `topology.json` can be loaded later from the **Setup** panel.
- The `topology.json` shapes the emulated environment (product, screen, languages, business
  domains, hardware configurations).

The console is bilingual (**English / French**, switchable at runtime from the header). It is
launched with `safecor-emulator --gui`; the headless CLI is unchanged without `--gui`.

## Documentation

- [Operator console guide](../../docs/emulator-operator.md) — how to launch and drive the
  console (layout, setup, controls, observation, i18n).
- [Architecture — how the emulator fits](../../docs/architecture.md#6-how-the-emulator-fits).
- [Function catalogue](../../docs/features.md) — what the platform exposes and what the
  emulator fakes.
- [Operator-console plan](../../plans/emulator-plan.md) — the design and phase breakdown.
