# Core controller

> **Scope**: the Dom0-side command handler (`Dom0Controller`).
>
> **Last updated**: 2026-11-20
>
> **Main artifacts**: `start-safecor-core-controller.py`, `_dom0_controller.py` (`safecor` library).

The core controller is the control side for shared services: it runs on **Dom0**, connects to the central broker on `/tmp/mqtt-dom0.sock`, and answers the platform commands of the DomUs.

## What it serves

| Function group | Topics (selected) |
|----------------|-------------------|
| File API (repository) | `system/disks/{list_files,read_file,copy_file,delete_file,file_fingerprint,create_file}` |
| Workflow | `system/workflow/{shutdown,restart_domain}` |
| System information | `system/info` (request/response) |
| Energy state | `system/energy/state` |
| Component discovery | `system/discover/components` |
| Ping / keepalive | `system/misc/ping` |
| Settings / languages | `system/settings/languages/{list,default,current,set}`, `system/settings/changed` (notification) |
| GUI switch | `system/gui/switch` |
| Logging | `system/events/*` |

The full contract (payloads included) is in [../../development/protocol.md](../../development/protocol.md). The USB/disk commands themselves are answered by `sys-usb` (see [sys-usb-controller.md](sys-usb-controller.md)); the core controller answers the repository side and the platform-wide functions.

## Dispatch pattern

`Dom0Controller.__message_worker` is a **linear `if/elif` chain** matching topic strings to `__handle_*` methods; each message runs in its own thread.

**To add a handler**:

1. Define the topic in `_topics.py`.
2. Subscribe to it in `__on_mqtt_connected`.
3. Add the `elif` branch in `__message_worker`.
4. Implement the `__handle_*` method.

> **Caveat**: the module-level `topology` global is **not populated** in the controller process (it is only populated in boot scripts like `create-domains.py`). A handler that needs the topology must load it itself (`System.get_topology()`).

## The `reboot_domain` note

`reboot_domain` is currently **commented out** in `_dom0_controller.py` (the force-restart path from Dom0). It is expected to be reworked when libvirt is removed from Dom0 (issue #265 — see [../decisions/0005-remove-libvirt-from-dom0.md](../decisions/0005-remove-libvirt-from-dom0.md)).
