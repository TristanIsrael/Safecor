# Project Status

> **Scope**: the current status of the Safecor project — the active version, the work in progress, and the known platform gaps. Updated at milestones, not per commit.
>
> **Last updated**: 2026-11-24

## Active version

The development branch is **`version-2`** (Safecor v2, packages 2.0-r0). The main lines of v2 are:

1. **The migration of all domain-to-Dom0 channels to PV channels (vchan)** (issue #256) — the serial channels of v1 (`channel = [...]` in the xl configs, kernel frontend `/dev/hvc1`) are replaced by PV channels created at runtime by the `vchan-socket-proxy` servers, plus a local MQTT broker per DomU (see [architecture/overview.md](architecture/overview.md) and the ADRs in [architecture/decisions/](architecture/decisions/README.md)).
2. **The direct USB mount** — a DomU with `direct_mount` in its topology mounts `/media/usb` from `sys-usb` over a vchan SFTP channel (per-session bwrap sandboxes), synchronized by the `safecor_direct_mount` component (see [architecture/components/direct-usb-mount.md](architecture/components/direct-usb-mount.md)).

## Work in progress

### The channels → vchan migration (issue #256)

Validated on real hardware with run sheets: `docs/plans/test-channels-migration/run-<n>.md` (runs 1–19; run 19 is **NOT GREEN** — §1–§4 green, the OFF path §5 failed on the stale domid after the `sys-usb` self-restart → #275; run 20 hardware-validates the #275 self-heal). The migration plan and its resolutions are in `docs/plans/test-channels-migration/test-channels-migration.md`; the sequence is in `docs/plans/test-channels-migration/finalization-plan.md`.

| Issue | Subject | State |
|-------|---------|-------|
| #256 | Migrate all domain-to-Dom0 channels to PV channels (vchan) | In review — runs 15–19 done (run 19 §4 green, §5 NOT GREEN); finalization: validate #275 at run 20, then close |
| #258 | DomU local MQTT broker with an upstream vchan bridge | Validated at run 14 (mosquitto running, multi-clients, e2e, bridge IDs `safecor-<domain>-bridge`) — to close with #256 |
| #264 | Investigate the libpython EACCES error on the sys-usb domain | Validated at run 14 (the `/etc` permissions restored at boot) — to close with #256 |
| #260 | Fix the SFTP vchan channel startup order and package the sftp-server | In progress — the per-session bubblewrap sandbox is implemented; see #270–#275 below; run 19 §4 (file I/O) is green; the OFF-path checks are at run 20 |
| #262 | Fix the domid write race in `reboot-domain.sh` | Re-scoped into #275 — run 19 §5 used the **non-forced** `restart_domain` (a self-restart) that the forced-path fix cannot cover; the self-heal supersedes it |
| #270 | Bounded domid wait and all-or-nothing READY with local log trace | Validated on hardware (runs 17–19) |
| #271 | Grant the controller xenstore access at boot | Validated on hardware (run 18 §1, clean reboot, no manual `chmod`) |
| #272 | Per-domain sandbox wrapper (socat 512-byte EXEC limit) | Validated on hardware (the channels start at boot since the #273 fix) |
| #273 | Reject the filtered `my_config` responses in the controller accept filter | Validated on hardware (the run-18 race no longer reproduces: the channels start and the business DomUs mount) |
| #274 | Mount the remote `/media/usb` instead of the SFTP session root | Validated on hardware (run 19 §4: the USB tree at the top level of the mount, file I/O, write refused, watchdog remount) |
| #275 | Self-heal the vchan domid on domain restart (Dom0 cache + SFTP channels) | In progress — the run 19 §5 failure (the stale domid after the `sys-usb` self-restart); the fix is designed and approved, implementation on `version-2`; hardware validation at run 20 (OFF path, single business reboot, Saphir simultaneous reboot) |
| #259 | Enforce MQTT client ID naming convention and broker authentication | Ready — second pass (hardening), after the #256 closure |
| #261 | Restrict xenstore write grants to the vchan subtree | Ready — second pass (hardening), after the #256 closure |

### Documentation

| Issue | Subject | State |
|-------|---------|-------|
| #263 | Update the project documentation and the Safecor Wiki for the v2 architecture | In progress — audit done 2026-11-24, the work is tracked in [plans/v2-documentation-update.md](../plans/v2-documentation-update.md) (project docs + the Wiki, including the missing `Migration-v1-v2` page) |
| #267 | Refactor the project documentation structure for AI coding agents | In progress — the `docs/` tree is in place (architecture, components, ADRs, specs, dev guides, plans) |
| #223–#227 | Wiki page corrections (Python-api obsolete, Safecor-core outdated, Packages outdated, Topology key names, Capabilities placeholders) | Open — the offline copies in `docs/` already use the code-authoritative content; the Wiki pages themselves must be fixed (covered by #263) |

### Security / technical debt

| Issue | Subject | State |
|-------|---------|-------|
| #265 | Remove libvirt from Dom0 (design rule #10) | Backlog — see [architecture/decisions/0005-remove-libvirt-from-dom0.md](architecture/decisions/0005-remove-libvirt-from-dom0.md). Note: the libvirt is still required by the Dom0 in v2; the domain restart works without it (shell script) |
| #257 | Port the unmerged 1.4 features (branch `feature-212`) to version-2 | Open — the inventory is in [plans/unmerged-1.4-features.md](../plans/unmerged-1.4-features.md) |
| #252 | Write integration tests for Safecor Core (shell scripts, init.d, configs) | Open |

### Library / emulator

| Issue | Subject | State |
|-------|---------|-------|
| #217 | B1: the language **list** request is never processed (Api/`Topics`/Dom0 handler mismatch) | Open — documented in [development/protocol.md](development/protocol.md) |
| #218 | `list_files` name filter silently ignored at runtime | Open |
| #219 | File fingerprint topic/field names (Wiki `file_footprint`/`footprint` vs code `file_fingerprint`/`fingerprint`) | Open |
| #220 | `storage_info` + `monitoring` documented but not implemented | Open |
| #222 | `switch_gui` field (`domain`) + `system_info` storage field (`files`) Wiki deviations | Open |
| #230 | `Api.publish()` double-encodes the JSON payload | Open |
| #233 | `MqttClient` loses its subscriptions after an automatic reconnection | Open — mitigated by the re-subscribe of the tracked topics in `MqttClient`; the issue stays open |
| #241 | Emulator: graphical operator console (topology-driven) | Implemented — the console is available (`safecor-emulator --gui --topology …`); see [development/testing.md](development/testing.md) |
| #243, #244, #248 | Emulator GUI bugs (source disk path field, field reset, disconnected-disk rejection) | Open |

## Known platform gaps

- **`sys-net`** — not available yet (would capture the network PCI buses like `sys-usb` captures USB).
- **`storage_info` / `monitoring`** — documented in the Wiki, not implemented in the code (no topic, no handler — #220/#227).
- **Language settings** — the list request is dropped by the code bug #217; the emulator's language state is not wired to the topology.
- **Data lifecycle analysis** — the security chapter "Analysis of the data lifecycle" is still to be completed.
- **1.4 features not ported** — the 16 features of the 1.4 line are not in v2 (see #257 and [plans/unmerged-1.4-features.md](../plans/unmerged-1.4-features.md)).

> Note: the domain restart from Dom0 (`restart_domain`) is **active** in v2 — `Dom0Controller.__reboot_domain` runs `doas /usr/lib/safecor/bin/reboot-domain.sh` (the libvirt path stays commented until #265).

## Where to look next

- The architecture and its components: [architecture/overview.md](architecture/overview.md)
- The MQTT contract: [development/protocol.md](development/protocol.md)
- The function catalogue (with the emulator coverage): [specifications/features.md](specifications/features.md)
- The active plans: `docs/plans/`
