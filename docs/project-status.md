# Project Status

> **Scope**: the current status of the Safecor project — the active version, the work in progress, and the known platform gaps. Updated at milestones, not per commit.
>
> **Last updated**: 2026-11-20

## Active version

The development branch is **`version-2`** (Safecor v2). The main line of v2 is the **migration of all domain-to-Dom0 channels to PV channels (vchan)** — the serial channels of v1 (`channel = [...]` in the xl configs, kernel frontend `/dev/hvc1`) are replaced by PV channels created at runtime by the `vchan-socket-proxy` servers, plus a local MQTT broker per DomU (see [architecture/overview.md](architecture/overview.md) and the ADRs in [architecture/decisions/](architecture/decisions/README.md)).

## Work in progress

### The channels → vchan migration (issue #256)

Validated on real hardware with run sheets: `docs/plans/test-channels-migration/run-<n>.md` (runs 1–14). The migration plan and its resolutions are in `docs/plans/test-channels-migration/test-channels-migration.md`; the remaining work (the sshfs direct mount #260, the domid race #262, the debug tty regression) and its sequence are in `docs/plans/test-channels-migration/finalization-plan.md`.

| Issue | Subject | State |
|-------|---------|-------|
| #256 | Migrate all domain-to-Dom0 channels to PV channels (vchan) | In review — runs 1–14 done; finalization active (sshfs direct mount, domid race, tty regression, then run 15) |
| #258 | DomU local MQTT broker with an upstream vchan bridge | In review — validated at run 14 (mosquitto running, multi-clients, e2e, bridge IDs `safecor-<domain>-bridge`) |
| #264 | Investigate the libpython EACCES error on the sys-usb domain | In review — resolved by restoring the `/etc` permissions at boot, validated at run 14 |
| #260 | Fix the SFTP vchan channel startup order and package the sftp-server chroot | Ready — the sshfs direct mount in the business domains does not work yet (run 14) |
| #262 | Fix the domid write race in `reboot-domain.sh` | Ready — all the vchans are lost after an API reboot (run 14) |
| #259 | Enforce MQTT client ID naming convention and broker authentication | Ready — second pass (hardening), after the #256 closure |
| #261 | Restrict xenstore write grants to the vchan subtree | Ready — second pass (hardening), after the #256 closure |

### Documentation

| Issue | Subject | State |
|-------|---------|-------|
| #263 | Update the project documentation and the Safecor Wiki for the v2 architecture | In progress |
| #267 | Refactor the project documentation structure for AI coding agents | In progress |
| #223–#227 | Wiki page corrections (Python-api obsolete, Safecor-core outdated, Packages outdated, Topology key names, Capabilities placeholders) | Open — the offline copies in `docs/` already use the code-authoritative content; the Wiki pages themselves must be fixed |

### Security / technical debt

| Issue | Subject | State |
|-------|---------|-------|
| #265 | Remove libvirt from Dom0 (design rule #10) | Backlog — see [architecture/decisions/0005-remove-libvirt-from-dom0.md](architecture/decisions/0005-remove-libvirt-from-dom0.md) |
| #257 | Port the unmerged 1.4 features (branch `feature-212`) to version-2 | Open |
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
| #233 | `MqttClient` loses its subscriptions after an automatic reconnection | Open |
| #241 | Emulator: graphical operator console (topology-driven) | Open — the console is implemented; see [development/testing.md](development/testing.md) |
| #243, #244, #248 | Emulator GUI bugs (source disk path field, field reset, disconnected-disk rejection) | Open |

## Known platform gaps

- **`sys-net`** — not available yet (would capture the network PCI buses like `sys-usb` captures USB).
- **`storage_info` / `monitoring`** — documented in the Wiki, not implemented in the code (no topic, no handler — #220/#227).
- **`reboot_domain`** — the force-restart path from Dom0 is currently commented in `_dom0_controller.py`; to be reworked with the libvirt removal (#265).
- **Language settings** — the list request is dropped by the code bug #217; the emulator's language state is not wired to the topology.
- **Data lifecycle analysis** — the security chapter "Analysis of the data lifecycle" is still to be completed.

## Where to look next

- The architecture and its components: [architecture/overview.md](architecture/overview.md)
- The MQTT contract: [development/protocol.md](development/protocol.md)
- The function catalogue (with the emulator coverage): [specifications/features.md](specifications/features.md)
- The active plans: `docs/plans/`
