# 0004 — Restore the `/etc` permissions on the DomU at boot

**Status**: Accepted (v2)

## Context

A DomU root filesystem is a **tmpfs** built at boot from the shared ISO plus the domain's **apkovl** (extracted from the config disk). The extraction of the apkovl over the read-only ISO content left `/etc` with incorrect permissions (not `0755`), which broke services that check or depend on the standard permissions of the configuration directory.

## Decision

The DomU boot sequence **restores the `/etc` permissions** (mode `0755`, owned by root) at boot, before the domain services start (issue #264). The fix lives in the `safecor-domu-base` boot path so every business domain benefits.

## Consequences

- The boot is idempotent: the permissions are re-applied at every boot (the tmpfs is rebuilt anyway, so the fix must be part of the boot sequence, not a one-time provisioning step).
- No change to the apkovl format or to the provisioning flow.
