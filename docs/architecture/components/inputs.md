# Inputs chain

> **Scope**: the path from the physical keyboard/mouse/touch to the GUI domain.
>
> **Last updated**: 2026-11-20
>
> **Main artifacts**: `InputsDaemon` (sys-usb), the vchan `input` channel, the orchestrator's inputs proxy, the `uinput` virtual devices, `Mouse` / `KeymapFR` (library).

## The chain

```
physical keyboard / mouse / touch (USB)
  → PCI passthrough to sys-usb
  → evdev events
  → InputsDaemon (sys-usb controller, _inputs_daemon.py)
  → /var/run/safecor/input.sock (UNIX)
  → vchan-socket-proxy client (stdio, sys-usb)
  → vchan "input" PV channel (ring in xenstore /local/domain/system/vchan/sys-usb/input)
  → vchan-socket-proxy server (Dom0)
  → /var/run/safecor/input.sock (Dom0)
  → orchestrator inputs proxy (filters and copies between Domains and the physical inputs)
  → virtual input devices (uinput, created at boot by the orchestrator)
  → the focused GUI domain
```

## Key points

- **sys-usb owns the physical inputs**: the USB buses are PCI-passthroughed to it (`xl pci-assignable-add` at Dom0 boot), so no other domain can read them.
- **The orchestrator creates the virtual input devices** (keyboard, mouse, touch) with `uinput` at boot, one set per GUI domain, and exposes them to the GUI domain's virtual display.
- **Focus**: only the focused GUI domain receives the inputs. The focus is stored in xenstore (`input-focus`) and is written by `orchestrator.py`; a GUI switch (`system/gui/switch`) moves both the display focus (see [display.md](display.md)) and the input focus.
- **The emulator** fakes this chain with `FakeInputDevice` (XenBus wire format) — see [../../development/testing.md](../../development/testing.md).

## Related

- [sys-usb-controller.md](sys-usb-controller.md) — the inputs daemon side
- [orchestrator.md](orchestrator.md) — the virtual input devices and the focus key
- [../decisions/](../decisions/README.md) — the uinput permission rule (`99-safecor.rules`) is part of the vchan privilege setup
