# 0005 — Remove libvirt from Dom0

**Status**: Proposed (issue #265, Backlog)

## Context

`libvirtd` runs on **Dom0 only** as a query client (`py3-libvirt`, `xen:///` connection). It is **not** in the domain creation path: the Domains are created with `xl create` from statically generated xl configurations (see [../components/orchestrator.md](../components/orchestrator.md)). Its current uses are limited to query functions (CPU count, domain list for `System` information), and the `reboot_domain` force-restart path (currently commented in `_dom0_controller.py`) is the only remaining action that would depend on it.

Running a daemon that can control the hypervisor in the privileged domain, for query-only purposes, contradicts **design rule #10 (always reduce attack surface)** and the simplicity rule.

## Decision (proposed)

Remove libvirt from Dom0:

- Drop the `libvirtd` service and the `py3-libvirt` dependency from `safecor-core`.
- Replace the query uses with direct `xl` / xenstore / `psutil` calls (e.g. `xl list` for the domain list, `psutil` for CPU/memory, xenstore for the screen).
- Rework `reboot_domain` to use `xl destroy` + `start-<domain>.sh` (or keep the domain-side self-restart only).

## Consequences

- `LibvirtHelper` (`_libvirt_helper.py`) is deleted from the library; the emulator's fake of it becomes unnecessary (see [../../development/testing.md](../../development/testing.md)).
- The pending libvirt-related issues (#75, #107, #135, #140) are closed referencing this one.
- No change to the DomU side: libvirt is not used there.
