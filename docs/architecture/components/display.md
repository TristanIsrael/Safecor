# Display

> **Scope**: Xorg on Dom0 and in the GUI Domains, display focus, screen size/rotation, splash.
>
> **Last updated**: 2026-11-20
>
> **Main artifacts**: the Dom0 `start-x` service (Xorg display manager), the per-GUI-domain Xorg servers, `XcbController` (library), `write-screen-information-to-xenstore.py`, `rotate-screen.py`, the `splash` service.

## Model

- **Dom0 owns the GPU**: the display adapter is PCI-passthroughed to Dom0. Domains never touch it directly.
- **The Dom0 Xorg display manager** shows the display of the **focused** GUI domain and switches the visible window on a `system/gui/switch` request (implemented with `XcbController`: show/hide the QEMU GTK windows).
- **Each GUI domain** (`has_gui: 1`) is an HVM domain (`vga = "stdvga"`, see [orchestrator.md](orchestrator.md)) running its own Xorg server on a virtual display; its framebuffer is displayed by Dom0.
- A GUI domain additionally gets virtual keyboard, mouse and touch (see [inputs.md](inputs.md)).

## Screen size and rotation

At boot, the orchestrator writes the screen size (fb0 `virtual_size`) and rotation to xenstore (`/local/domain/system/screen_size`, `screen_rotation` — see [orchestrator.md](orchestrator.md)); DomUs read them with `System._get_screen_size` / `System.get_screen_rotation`. The rotation comes from the topology (or a matching hardware configuration, see [../configuration-management.md](../configuration-management.md)) and is applied by `rotate-screen.py`.

## Splash

The `splash` service shows the boot logo (background colour from the topology `product.splash_bgcolor`) during the second phase of boot. When the focused GUI application publishes the `system/workflow/gui_ready` notification, Dom0 kills the splash. See [../../development/protocol.md](../../development/protocol.md) for the topic.

## GUI switch

`system/gui/switch` (request/response, `accepted`/`refused`): Dom0 changes the focused domain — the Xorg display manager shows the new domain's window and `input-focus` is updated. See [inputs.md](inputs.md) for the input side.
