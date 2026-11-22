# Finalization of the channels → vchan migration and the sshfs direct mount

> **Status**: Active — Phase B (implemented on `version-2` with the bwrap sandbox, to be validated at run 16)
>
> **Last updated**: 2026-11-21
>
> **Context**: finalization of issue #256. The migration replaces (1) the xl serial channels (`channel = [...]` in the xl configs) with vchan channels for messaging, inputs and the debug tty, and (2) the 9p USB share with a vchan+SFTP+sshfs "direct mount" of `/media/usb` in the business domains. Runs 1–14 are in this directory; the run sheets carry the findings and resolutions.
>
> **References**:
> - [test-channels-migration.md](test-channels-migration.md) (objectives + run resolutions)
> - [`docs/plans/direct-usb-mount.md`](../direct-usb-mount.md) (the direct mount design)
> - `docs/architecture/decisions/` (ADR-0001 local broker, ADR-0003 broker config at boot)

---

## 1. State after run 14

| Objective (test-channels-migration.md) | State |
|---|---|
| Messaging on all Domains | ✅ validated (runs 13, 14 — #258) |
| Inputs on sys-usb | ✅ validated (runs 13, 14) |
| GUI display | ✅ validated (runs 13, 14) |
| Debugging tty on sys-usb | ❌ regression (OK at run 13, KO at run 14) |
| File read on a USB storage from a Domain | ❌ not working (#260 — the sshfs direct mount) |

| Issue | Subject | State |
|---|---|---|
| #256 | Migrate all domain-to-Dom0 channels to PV channels (vchan) | In review — finalization in progress |
| #258 | DomU local MQTT broker with an upstream vchan bridge | In review — validated at run 14 |
| #264 | libpython EACCES on the sys-usb domain | In review — validated at run 14 |
| #260 | SFTP vchan channel: startup order + per-session sftp-server sandbox | In progress — implemented on `version-2` (bwrap sandbox, after the run-15 chroot failure), to be validated at run 16 |
| #262 | domid write race in `reboot-domain.sh` | In progress — implemented on `version-2` (polling), to be validated at run 15 |
| #259 | MQTT client ID naming convention + broker authentication | Ready — second pass (hardening) |
| #261 | Restrict the xenstore write grants to the vchan subtree | Ready — second pass (hardening) |

---

## 2. Phases

### Phase A — Run 14 wrap-up (documentation + statuses) ✅ done (committed `fd062cf`)

1. `test-channels-migration.md`: check the objectives validated at run 14 (messaging, inputs, GUI), add the "Run 14 resolutions" section (the debug tty regression as a new finding, the vchan loss after the API reboot as a #262 cascade).
2. `docs/project-status.md`: #258 → In review (validated at run 14), #264 → validated at run 14, link this plan.
3. GitHub: #258 → "In review" in the Safecor Kanban (implementation complete, awaiting validation).

**Exit criteria**: docs and issue statuses reflect run 14.

### Phase B — #260: make the sshfs direct mount work

**Implemented** on `version-2` (bwrap). Awaiting validation at run 16.

**Approach replaced after run 15**: run 15 validated the transport but showed the sftp-server chroot built at boot was **empty** (only the binary, no dynamic linker or libraries) — `parse_ldd` parsed the glibc `ldd` output format, which Alpine/musl does not use, so the chrooted sftp-server could not exec. The boot-time chroot was therefore **replaced by a per-session bubblewrap sandbox**:

- no boot-time assembly: each session is sandboxed by `bwrap` at spawn — the sandbox root is a **private tmpfs** (nothing it creates reaches the host disk or the client's sshfs view), `/media/usb` is bound at the same path and made the working directory (the served SFTP root), plus the sftp-server binary, the setpriv helper and the shared libraries setpriv needs (resolved at start with `which`/`ldd`, so the bind list stays correct across Alpine/util-linux versions), a minimal one-account `/etc/passwd` (written at start), and the musl dynamic linker, all in read-only, a fresh `/dev`, and unshared pid/ipc/uts/net namespaces;
- stronger confinement than a chroot (a chroot can be escaped by a root process);
- the `sftp-server` runs as the dedicated `svc-sys-usb-sftp` account with no capabilities: `setpriv` (bound in read-only, path resolved dynamically — it is in `/bin` on the Alpine 3.24 target) drops to the account inside the sandbox before exec, and only `CAP_SETUID`/`CAP_SETGID`/`CAP_SETPCAP` remain in the bounding set for the short-lived root switch — the disks are owned by the account (mdev mount options), so no DAC override is needed; and the `ro` channels get a read-only `/media/usb` bind;
- bwrap installs a reaper as pid 1 of the sandbox, removing the zombie accumulation observed at run 15;
- the SFTP root stays `/media/usb`: a disk mounted at `/media/usb/<label>` on sys-usb appears at the same path in the client's sshfs mount;
- `start_channel` is idempotent (stop the existing instance by pidfile and remove the stale socket before starting: run 15 exposed duplicated socat listeners in a restart loop), and the children's output is redirected to a per-domain log;
- on USB disk add/remove/change, the mdev hook kills the existing sftp sessions (each sandbox is a mount-table snapshot at spawn), so the clients' sshfs (`reconnect` option) reconnect into fresh sandboxes.

**Run-16 hardware finding (2026-11-22)**: the smoke test failed on the real target, which is **Alpine 3.24** (bwrap 0.12.0, setpriv 2.42.3 in `/bin` linked against libeconf+libcap-ng, openssh-sftp-server 10.3) — the pre-tests had been run with Alpine 3.20 binaries. The sandbox command was made version-robust as a new commit on #260 (dynamic setpriv path + ldd-resolved libraries, explicit `--dir` for the bind destinations, the minimal `/etc/passwd`, the tmpfs sandbox root); the fixed smoke command and the silence probes A/B/C are in [run-16.md](run-16.md).

The original (run-15) implementation, for reference, was on `fix-260-sftp-vchan` (the three fixes below plus the `reconnect` sshfs option, the APKBUILD sha512 recalculation and unit tests for the new pure functions):

The transport design is validated: sshfs with a custom `ssh_command` bridging stdio over vchan to a raw `sftp-server` is the documented "bypass SSH" pattern, the same as the working `msg` channel. The remaining work is operational:

1. `safecor-vchan-sftp.py` (`safecor-sys-usb` package, server side):
   - `query_direct_mount_domains()` returns `(name, mode)` pairs — the `my_config` response already carries the `direct_mount` object with `mode` (`ro`/`rw`, default `rw`); today only the names are kept.
   - **Build the chroot** before starting the channels, only when at least one domain has `direct_mount` (the topology is unknown outside the MQTT query). The DomU root is a tmpfs rebuilt at every boot, so the chroot must be rebuilt at every boot: `mkdir -p /media/usb`, copy `/usr/lib/ssh/sftp-server` to `/media/usb/usr/lib/ssh/sftp-server`, and copy the shared libraries reported by `ldd` at runtime (so the exact versions of the packaged `openssh-sftp-server` are used). The chroot root is `/media/usb` (not `/media`): the client mounts the remote root `:/`, so the domain sees `/media/usb/<disk>/...` mapped to sys-usb's `/media/usb/<disk>/...`.
   - **Fix the startup order**: start socat (`UNIX-LISTEN:/var/run/safecor/vchan-<name>.sock,fork EXEC:"chroot /media/usb /usr/lib/ssh/sftp-server <flags>"`) **before** `vchan-socket-proxy -m server` (the proxy connects to the socket socat creates — run 12 finding 7a).
   - **sftp-server flags**: `-u 077` always; `-R` (read-only mode: open for write and every state-changing request are denied) for `ro` domains; optionally a `-P` denied-request list (`hardlink,link,symlink`) as an extra hardening for both modes.
2. `DirectMountManager` (`python/lib`, client side): add `reconnect` to the sshfs options (the mount heals itself when sys-usb is rebooted: the `vchan-sftp` script resolves the sys-usb domid at runtime, and the `safecor-vchan-sftp` service recreates the server side at boot).
3. Packaging: recalculate the `sha512sums` of the modified files in the `safecor-sys-usb` APKBUILD and bump `pkgrel`; same for `safecor-lib` if `DirectMountManager` changes.

**Exit criteria**: on real hardware, a business domain with `direct_mount` mounts `/media/usb` automatically at boot and a file from a connected USB disk is readable (and writable, for `rw`) through the mount; an `ro` domain cannot write. Validated at run 16.

### Phase C — #262: the domid write race in `reboot-domain.sh`

**Implemented** on `version-2` (smoke-tested with a fake `xl` in a chroot: the new domid is written after the domain comes back, no write and exit 1 when the domain never comes back or `xl reboot` fails). Awaiting validation at run 15.

`reboot-domain.sh` slept 3 s after `xl reboot` and then read the domid — too short: the domain is still down/restarting, the domid is not written (or the stale one is kept), and the Dom0 discovery loop in `create-vchan-tunnels.py` (which recreates the vchan servers when the domid changes) never sees the new domid. Result (run 14): all the vchans of the restarted domain are lost.

1. `reboot-domain.sh`: replace `sleep 3` with polling — record the old domid, wait for the domain to go down (~30 s), wait for it to come back with a domid different from the old one (~60 s), then write `/local/domain/system/domids/<name>` (exit 1, and no write, if no new domid is seen: the Dom0 controller then answers the `restart_domain` request with a refusal).

No change needed in `create-vchan-tunnels.py` (it already reaps and re-discovers on domid change) nor in `safecor-vchan-sftp.py` (the service re-runs at the sys-usb boot).

**Exit criteria**: `system/workflow/restart_domain/request` on sys-usb and on a business domain leaves every vchan alive (msg for all domains, input/tty on sys-usb, sftp for the direct-mount domains). Validated at run 15.

### Phase D — the debugging tty regression (run 14)

The debug tty worked at run 13 and is KO at run 14, while every component is present (Dom0: `vchan-socket-proxy -m server` for the tty channel, `create-tty-tunnel.sh`, `create-tty-terminal.sh`, `getty` on `/var/run/safecor/tty-admin`; sys-usb: the `tty` vchan client and `socat /dev/ttyUSB0`). The break is in the chain assembly, probably related to the run-13→14 changes (mosquitto/socat apk dependencies, `safecor-domu-base` made a dependency of `safecor-sys-usb`, the duplicated `setup-vchan` removed from `safecor-sys-usb`). No dedicated GitHub issue (user decision); tracked in the run sheets.

1. On real hardware: identify which process/socket of the chain is dead (`ps` on both domains, socket existence, service states and ordering).
2. Fix, then re-validate the tty at run 15.

**Exit criteria**: the debug tty works in debug mode at run 15 (objective re-validated).

### Phase E — Run 15: final validation + #256 closure

The run sheet is [run-15.md](run-15.md). Prerequisite: Phase C implemented (and `safecor-core` rebuilt with it). Packages to rebuild from `version-2`: `safecor-lib` and `safecor-sys-usb` (the Phase B fix), plus `safecor-core` for Phase C. A full cold boot in debug mode, then:

- [ ] the five objectives of `test-channels-migration.md` are all validated (messaging, inputs, debug tty, file read on a USB storage from a Domain, GUI display);
- [ ] USB hot-plug: connect a USB disk after boot, it appears in the `/media/usb` mount of the business domains without reboot;
- [ ] the API reboot (`system/workflow/restart_domain/request`) on sys-usb and on a business domain leaves all the vchans alive (Phase C);
- [ ] the `ro`/`rw` modes of the direct mount are enforced (Phase B);
- [ ] regressions: the GUI domain displays, the Saphir app starts, the local brokers stay connected.

Then: close #256 (and #258, #264, #260, #262 as validated), update `docs/project-status.md`, the run sheet and the Wiki references.

### Phase F — Second pass (hardening), after the #256 closure

- **#259** — MQTT client ID naming + broker authentication: audit every MQTT client (the Dom0 controller, the DomU local brokers and bridges, the one-shot clients like `safecor-vchan-sftp` and `direct-mount`) and enforce the `safecor-*` convention; remove `allow_anonymous true` from the DomU local brokers (per-domain credentials generated at boot); make the Dom0 broker TCP 1883 listener debug-mode only.
- **#261** — xenstore write grants: `set-xenstore-permissions.sh` currently gives every domain `b` (read/write/create/delete) on the whole `/local/domain/system` subtree. Restrict it: default `r` for all domains, `b` per domain only on its own `/local/domain/system/vchan/<domain>` subtree (a DomU client writes its own ring data there).

**Exit criteria**: a dedicated validation run (run 16) covering the broker authentication and the xenstore grants.

---

## 3. Sequencing and branches

| Phase | Branch | Issue |
|---|---|---|
| A | `version-2` (docs only) | #256 |
| B | `fix-260-sftp-vchan` | #260 |
| C | `fix-262-domid-race` | #262 |
| D | with the tty fix branch | — (no issue, user decision) |
| E | validation on real hardware | #256 |
| F | `fix-259-mqtt-auth`, `fix-261-xenstore-grants` | #259, #261 |

Every code commit is linked to its issue; the non-regression suite is run before every push (project rules).
