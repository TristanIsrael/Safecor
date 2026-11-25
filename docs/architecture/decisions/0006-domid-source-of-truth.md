# 0006 — Domid cache demoted to self-healed convenience cache

> **Scope**: the vchan tunnel manager and the SFTP channel supervisor, both
> of which pin vchan servers to a domain's domid.
>
> **Last updated**: 2026-11-25
>
> **Status**: Proposed (issue #275)

## Context

The domid cache at ``/local/domain/system/domids/<name>`` was originally the
**source of truth** for Dom0-side components (vchan tunnel manager, SFTP channel
manager) that needed to pin a vchan server to a domain's domid.  This worked
until the self-restart flow was introduced: when a CORE domain (e.g. ``sys-usb``)
restarts itself via the ``restart_domain`` API, Dom0 accepts the request (no
Dom0 reboot) and the domain reboots.  The reboot creates a **new domid**
assigned by the hypervisor.

DomUs cannot write back the new domid to Dom0's xenstore (no
``xenstore-write`` privilege).  The vchan tunnel manager on Dom0 continues to
pin to the **stale** cached domid.  The vchan server fails (old domid gone),
and the SFTP channels for direct USB mount break.  There is no automatic
recovery — the issue was tracked as #275.

## Decision

Promote the domid cache from "source of truth" to **self-healed convenience
cache**:

1. **vchan tunnel manager** (`create-vchan-tunnels.py`) — the discovery loop
   now **always** resolves the live domid from the Xen tree
   ``/local/domain/<N>/name`` (which the hypervisor maintains, unforgeable).
   If the resolved domid differs from the cached value, the cache is updated
   in place and a log line is emitted.

2. **SFTP channel supervisor** (`SysUsbController.__channel_supervisor()`) — a
   dedicated daemon thread runs every 5 s, reconciling all tracked channels
   against the Dom0 cache (read via ``System().get_domain_domid()``).  When a
   channel dies (old domid gone) or when a domid changes, the supervisor
   restarts the channel with the current domid.

3. **restart_domain contract** — CORE domains are self-restartable: Dom0
   publishes an ``accepted`` response and the domain restarts itself.
   BUSINESS domains are only restartable when `forced=True` (Dom0-initiated
   reboot), because Dom0 has no self-heal mechanism for them.

## Consequences

- **vchan tunnel manager** no longer relies on the cached domid as source of
  truth.  The cache is a convenience that gets self-healed on every
  discovery-loop iteration.
- **SFTP channels** survive domain self-restart via the supervisor thread.
- **Security** — the `svc-vchan-tunnels` user now needs a narrow `xenstore-write`
  grant for the domid cache path only.  A new doas grant file
  (`conf/doas-svc-vchan-tunnels.conf`) was created.
- **Self-restart of CORE domains** (the original issue #275 scenario) now
  works end-to-end: Dom0 accepts → domain self-reboots → vchan tunnel manager
  self-heals the cache → supervisor thread restarts SFTP channels.

## References

- Issue #275
