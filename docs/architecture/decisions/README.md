# Architecture Decisions

> **Scope**: the registry of the decisions made on the Safecor architecture. One short document per decision.
>
> **Last updated**: 2026-11-20

## Format

Each entry is `NNNN-<slug>.md` and contains:

- **Context** — the problem or constraint that forced a decision.
- **Decision** — what was decided, and when (issue / version).
- **Consequences** — what it changes (packages, scripts, security posture, follow-ups).

Entries are numbered in chronological order. A decision that is superseded keeps its number and gets a **Superseded by** line.

## Index

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-per-domu-local-mqtt-broker.md) | One local Mosquitto broker per DomU, bridged to Dom0 over the vchan `msg` channel | Accepted (v2) |
| [0002](0002-packages-squashfs-block-disk.md) | The local Alpine repository is a `packages.squashfs` block disk (`xvde`), no 9p share | Accepted (v2) |
| [0003](0003-broker-config-generated-at-boot.md) | The DomU broker configuration is generated at boot, not packaged | Accepted (v2) |
| [0004](0004-apkovl-directory-permissions.md) | Restore the `/etc` permissions on the DomU at boot | Accepted (v2) |
| [0005](0005-remove-libvirt-from-dom0.md) | Remove libvirt from Dom0 | Proposed (issue #265) |
