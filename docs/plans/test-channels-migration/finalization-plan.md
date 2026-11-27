# Finalization of the channels → vchan migration and the sshfs direct mount

> **Status**: Active — the #275 self-heal is implemented on `version-2` (rebuilt around the `XenStore` class, NFR-4, doas grant removed); awaiting the dedicated hardware validation (run 21 → run 20)
>
> **Last updated**: 2026-11-26
>
> **Context**: finalization of issue #256. The migration replaces (1) the xl serial channels (`channel = [...]` in the xl configs) with vchan channels for messaging, inputs and the debug tty, and (2) the 9p USB share with a vchan+SFTP+sshfs "direct mount" of `/media/usb` in the business domains. Runs 1–21 are in this directory; the run sheets carry the findings and resolutions.
>
> **References**:
> - [test-channels-migration.md](test-channels-migration.md) (objectives + run resolutions)
> - [`docs/plans/direct-usb-mount.md`](../direct-usb-mount.md) (the direct mount design)
> - `docs/architecture/decisions/` (ADR-0001 local broker, ADR-0003 broker config at boot, ADR-0006 domid self-heal)
> - `docs/architecture/system-workflow.md` (the system state machine + transitions, with the 12-item coherence check)

---

## 1. State after run 19 (runs 20/21 pending)

| Objective (test-channels-migration.md) | State |
|---|---|
| Messaging on all Domains | ✅ validated (runs 13–14, re-validated runs 17–19) |
| Inputs on sys-usb | ✅ validated (runs 13–14, re-validated runs 17–19) |
| GUI display | ✅ validated (runs 13–14, re-validated runs 17–19) |
| Debugging tty on sys-usb | ❌ still open (regression since run 14; re-checked at run 20 §6) |
| File read on a USB storage from a Domain | ✅ validated at run 19 §4 (readable at the same path, `ro` enforced, watchdog remount) |

Issue states (Safecor Kanban, 2026-11-26):

| Issue | Subject | State |
|---|---|---|
| #256 | Migrate all domain-to-Dom0 channels to PV channels (vchan) | Validated (kanban) — the migration itself is validated; the debug tty remains an open item tracked in the run sheets (no dedicated issue, user decision) |
| #258 | DomU local MQTT broker with an upstream vchan bridge | Validated (run 14) |
| #260 | SFTP vchan channel: startup order + bwrap sandbox | Validated (runs 16–19) |
| #262 | domid write race in `reboot-domain.sh` (forced path) | Validated |
| #264 | libpython EACCES on the sys-usb domain | Validated (run 14) |
| #270 | SFTP channels not started at boot (domid boot-order race) | Ready — fix implemented, final re-validation at run 20 §1 |
| #271 | Controller cannot read xenstore (EACCES on `/dev/xen/xenbus`) | Validated (run 18) |
| #272 | SFTP sessions die at birth (socat EXEC > 512 bytes) | Validated (run 19, the sandbox wrappers) |
| #273 | Controller accepts the wrong `my_config` response (race) | Validated (run 19 §3) |
| #274 | Business DomUs mount the SFTP session root instead of `/media/usb` | In review — fix implemented, final validation at run 20 |
| #275 | Self-heal the vchan domid on domain restart | In review — implemented on `version-2`, rebuilt around the `XenStore` class; awaiting run 21 (mechanism) + run 20 §4–§6 (end-to-end) |
| #259 | MQTT client ID naming + broker authentication | Ready — second pass (hardening, Phase F) |
| #261 | Restrict the xenstore write grants to the vchan subtree | Ready — second pass (hardening, Phase F) |
| #276 | Adopt `XenStore.monitor()` at the three domid polling sites | Backlog — next iteration (Phase H) |
| #277 | Resolve the 12 doc/code inconsistencies (system-workflow coherence check) | Ready — next iteration (Phase H) |

---

## 2. Phases

### Phase A — Run 14 wrap-up (documentation + statuses) ✅ done (committed `fd062cf`)

(No change: `test-channels-migration.md` + `project-status.md` updated, #258 → In review. Exit criteria met.)

### Phase B — #260: make the sshfs direct mount work ✅ done, validated

The per-session **bwrap sandbox** (run-15 chroot failure → run-16 Alpine 3.24 version-robustness fix) is validated on hardware: run 19 §2 (the sandbox wrappers) and §4 (file I/O through the mount, `ro` enforced, watchdog remount). History: [run-15.md](run-15.md), [run-16.md](run-16.md), [run-17.md](run-17.md) (final status).

### Phase C — #262: the domid write race in `reboot-domain.sh` ✅ done, validated

Polling in `reboot-domain.sh` (wait for the domain down ~30 s, wait for a **new** domid ~60 s, then write the cache) — validated on the kanban; the run-19 §5 failure was the **self-restart** path (out of #262's scope), which became #275.

### Phase D — the debugging tty regression (run 14) ❌ still open

No change: the chain is present on both domains but the tty is KO since run 14. Re-checked at run 20 §6 (it does not block the direct-mount closure — user decision). Needs a dedicated diagnosis on hardware (which process/socket of the chain is dead).

### Phase E — Run 15: final validation + #256 closure ✅ done

Run 15 was performed (NOT GREEN at the time) and produced the direct-mount issue set #270–#274, then runs 17–19 validated the direct mount. #256 is Validated on the kanban.

### Phase F — Second pass (hardening) ⏳ pending

- **#259** — MQTT client ID naming + broker authentication: audit every MQTT client, enforce the `safecor-*` convention, remove `allow_anonymous true` from the DomU local brokers, Dom0 TCP 1883 debug-mode only.
- **#261** — xenstore write grants: default `r` for all domains, `b` per domain only on its own subtree. (Note: the current run-19/20/21 state relies on the existing `set-xenstore-permissions.sh` grants; #261 must not break the `XenStore` self-heal write-back from `svc-vchan-tunnels` — re-check the `system` subtree access.)

**Exit criteria**: a dedicated validation run covering the broker authentication and the xenstore grants.

### Phase G — #275: the stale-domid self-heal (current step)

**Context**: the run-19 §5 failure — after a **self-restart** of sys-usb (non-forced `restart_domain`), the domid changed (1 → 5) but the Dom0 domid cache stayed stale: the three vchan servers remained pinned to the old domid, `safecor_direct_mount` never reached `ready` again, and the business DomUs never remounted. Full analysis: [run-19.md](run-19.md) §5 resolution.

#### G1 — v1 (CLI-based self-heal) ✅ implemented, committed `51648be` — superseded by G2

- `create-vchan-tunnels.py`: the discovery loop resolves the **live** domid from the Xen tree and writes the cache back only on difference (ADR 0006: the cache is demoted to a self-healed convenience cache).
- `SysUsbController`: a SFTP channel supervisor thread (5 s tick) reconciles every `direct_mount` channel (start a missing one, re-pin on domid change or server death).
- `restart_domain` contract: the non-forced branch always publishes a response (honest `refused` + reason for a non-self-restartable business domain); the `forced` field added to the API/request.

#### G2 — Rebuilt around the `XenStore` class ✅ implemented, unit-tested, committed `ac50787` + `c0e2e2a`

- `XenStore` rewritten (per-instance monitor state, robust `monitor()`, `write() → bool`, str returns, `read_children`) — **the class itself was informally hardware-validated on Saphir** (the user's XenStore tests).
- **Every** library and Dom0-script xenstore I/O now goes through the class (new **NFR-4** in `features.md` — Python code only, shell keeps the CLI for its fixed boot-time one-shots); the last Python CLI user (`write-screen-information-to-xenstore.py`) migrated; the **doas grant `conf/doas-svc-vchan-tunnels.conf` removed** (attack-surface reduction, design rule #10); `safecor-lib` depends on the `xen` bindings.
- Emulator: in-memory `xen` bindings stub + xenstore tree seed; the `fake_run` xenstore hook removed.
- New `docs/architecture/system-workflow.md` (system states + transitions) with its 12-item coherence check (tracked in #277).
- Tests: lib suite 454 passed; emulator suite 89 (1 pre-existing dev-machine flake, passes solo).

#### G3 — Dedicated hardware validation ⏳ pending (the next hardware step)

The two runs are deliberately **separated** (user decision): the mechanism is validated on its own before the end-to-end scenarios rely on it.

1. **[Run 21](run-21.md) — the XenStore mechanism** (not yet executed): device open on Dom0/sys-usb as a service user, **zero** `xenstore-*` processes, **no** doas conf, the migrated call sites return the right values, the self-heal write-back through `XenStore.write`.
2. **[Run 20](run-20.md) — the end-to-end scenarios** (preparation done: cold boot with the rebuilt packages, §1 xenstore grant + sandbox wrappers OK; scenarios pending):
   - §1 the channels start on their own, the component `ready`, the cache consistent at boot;
   - §2 the **OFF path** (the run-19 failure): sys-usb self-restart → self-heal log, cache == `xl domid`, servers re-pinned, SFTP channels survive, remount automatic;
   - §3 a forced business-domain reboot + the non-forced business restart **refused** with a reason;
   - §4 the **Saphir simultaneous-reboot case** (sys-usb + both AV domains at once, any order) converges with no manual action;
   - §5 regressions (brokers, messaging, inputs, GUI, **debug tty**, the forced path unchanged).

**Precondition for run 20**: run 21 is fully green.

#### G4 — Closure

When green: validate #275 (and #270, #274), push `version-2` (commits `ac50787` + `c0e2e2a` + any fix), update the run sheets, `docs/project-status.md` and the Kanban, and close the #275 GitHub issue.

**Exit criteria**: run 21 all green + run 20 §1–§5 all green, no manual action, any reboot order.

### Phase H — Next iteration (after the #275 closure)

- **#276** (Backlog): adopt `XenStore.monitor()` at the three domid polling sites (the discovery loop, `__wait_for_domid`, the SFTP supervisor) — event-driven instead of 1–5 s loops; its own dedicated hardware validation.
- **#277** (Ready): resolve the 12 doc↔code coherence items flagged by `system-workflow.md` (each item gets its own issue where a code change is decided).
- Phase F (#259, #261) remains Ready — #261 to be re-checked against the `XenStore` self-heal write-back.
- Phase D (debug tty) — dedicated diagnosis, independent of the above.

---

## 3. Sequencing and branches

| Phase | Branch | Issue |
|---|---|---|
| A | `version-2` (docs only) | #256 |
| B | `fix-260-sftp-vchan` → `version-2` | #260 |
| C | `fix-262-domid-race` → `version-2` | #262 |
| D | with the tty fix branch | — (no issue, user decision) |
| E | validation on real hardware | #256 |
| F | `fix-259-mqtt-auth`, `fix-261-xenstore-grants` | #259, #261 |
| G | `version-2` | #275 |
| H | one dedicated branch per issue | #276, #277, #259, #261, D |

Every code commit is linked to its issue; the non-regression suite is run before every push (project rules).
