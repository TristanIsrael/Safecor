# Safecor Components

> **Scope**: one file per component, with its low level design when it has one. Start from [../overview.md](../overview.md) for the global picture.
>
> **Last updated**: 2026-11-20

| Component | What it is | File |
|-----------|-----------|------|
| **Orchestrator** | Dom0 service that creates the Domains' environments (xl configs, disks, virtual inputs) and drives their lifecycle (provisioning → boot → runtime). | [orchestrator.md](orchestrator.md) |
| **Messaging** | The MQTT message bus: the Dom0 central broker, the per-DomU local brokers, and the vchan `msg` channel bridge. | [messaging.md](messaging.md) |
| **vchan tunnel manager** | The `vchan-socket-proxy` servers on Dom0 that bridge every DomU's PV channels (msg, input, tty, sftp) to local UNIX sockets. | [vchan-tunnel-manager.md](vchan-tunnel-manager.md) |
| **Inputs chain** | The path from the physical keyboard/mouse/touch to the GUI domain: sys-usb evdev → vchan input channel → Dom0 proxy → virtual inputs. | [inputs.md](inputs.md) |
| **Display** | Xorg on Dom0 and in the GUI Domains, display focus, screen size/rotation, splash. | [display.md](display.md) |
| **Core controller** | The Dom0-side command handler (`Dom0Controller`): file API, workflow, system info, energy, discovery, settings, logging. | [core-controller.md](core-controller.md) |
| **sys-usb controller** | The USB controller domain: USB storage management, file API over disks, inputs daemon, debug TTY. | [sys-usb-controller.md](sys-usb-controller.md) |
| **Direct USB mount** | The v2 `direct_mount` feature: a DomU mounts `/media/usb` from `sys-usb` over a vchan SFTP channel (sshfs). | [direct-usb-mount.md](direct-usb-mount.md) |

The architecture decisions taken on these components are recorded in [../decisions/](../decisions/README.md).
