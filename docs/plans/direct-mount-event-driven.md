# Plan — event-driven refactoring of the direct USB mount (#253)

> **Status**: **implemented** (single commit linked to issue #253, branch `version-2`). Code, tests and docs are done and the quality gates pass (ruff clean, full suite = baseline). **Hardware validation pending** — the run is [`test-channels-migration/run-17.md`](test-channels-migration/run-17.md).
> **Branch**: `version-2`. **Versioning**: no bump (refactoring branch).
> **Supersedes**: the retry-loop design of `docs/plans/direct-usb-mount.md` (kept as history).

## 1. Goal

Make the direct USB mount **event-driven** (NFR-3) and reduce it to a
**single synchronization point**: the state of a dedicated component
`safecor_direct_mount`, published by the `SysUsbController` (sys-usb) on the
MQTT bus.

- `/media/usb` is mounted **proactively at the end of domain startup and kept
  permanent** on every `direct_mount` business DomU, whether or not a USB
  disk is connected (the sshfs mount of sys-usb's `/media/usb` directory
  succeeds even when empty).
- The SFTP server management (socat + `bwrap sftp-server` per session) moves
  from the separate `safecor-vchan-sftp` openrc service **into
  `SysUsbController`** (no `sftp_channel.py` — the logic is integrated).
- `safecor-vchan-sftp.py` and `safecor-vchan-sftp.initd` are **deleted**.

## 2. NFR-3 (new, `docs/specifications/features.md` §11 + `python-api.md`)

> **NFR-3 — Synchronization by messages, not by polling.** Cross-component
> and cross-domain readiness is established **only** through the **messages
> and notifications of the MQTT bus** (component states on
> `system/discover/components`, events). **Polling and retry loops are
> forbidden** to establish the readiness of a remote component: a component
> **publishes its state**, the consumers **react to the notification**. A
> **one-shot** request/response (e.g. `my_config`, `discover_components`) is
> allowed to fetch the current state at subscribe time.

Scope note: NFR-3 concerns *cross-domain readiness over the bus*. Local
state checks (e.g. `System.is_usb_mountpoint_ready()` reading
`/proc/mounts`) are out of scope.

## 3. Constants and enums

`_constants.py`:

```python
class MountMode(Enum):
    """The direct mount mode of a domain."""
    RO = "ro"
    RW = "rw"
```

```python
class Constants:
    ...
    SAFECOR_DIRECT_MOUNT = "safecor_direct_mount"
```

`MountMode` is exported by `__init__.py`. No raw `"ro"`/`"rw"` string
comparisons remain: the config parsing, the sftp-server arguments and the
sshfs options all use the enum.

Config query semantics (both sides): `None` = **failure** (no definitive
answer), `False` = **not enabled**, `MountMode.RO` / `MountMode.RW` =
enabled.

## 4. The `safecor_direct_mount` component (state machine)

Hosted by `SysUsbController` (which already hosts `safecor_disk_controller`
and `safecor_input_controller` — a controller may host several components).
Published on `system/discover/components/response` alongside the other two.

| State | Set when | Publish |
|---|---|---|
| `STARTING` | controller startup (SFTP channels not yet up) | at `__on_mqtt_connected` (the existing proactive `__handle_discover_components` call) |
| `READY` | the SFTP channel start pass completed for every `direct_mount` domain (channels started, or skipped with a logged warning); also when there is **zero** `direct_mount` domain | `__set_direct_mount_state(READY)` |
| `OFF` | `system/workflow/restart_domain` for `sys-usb` (reboot), or `stop()` | `__handle_restart` publishes all three components `OFF` before the reboot |

`__handle_discover_components` reports the **current** state of
`safecor_direct_mount` (not a hardcoded `READY`), via a shared
`__publish_component_states()` method.

Diagnostic value: `safecor_disk_controller=READY` +
`safecor_direct_mount=STARTING` ⇒ the SFTP side is broken (disks are fine).

### SysUsbController changes (sys-usb side)

1. **One-shot `my_config` query on the controller's own client** (no second
   broker connection, no polling):
   - `__on_mqtt_connected` also subscribes to `system/topology/my_config/response`.
   - The SFTP thread publishes `my_config/request` with `{}` (full topology)
     and waits on a `threading.Event` (10 s timeout) signalled by
     `__on_mqtt_message` when the response arrives (the response is
     intercepted there, before the queue routing).
   - Blocking is allowed: it runs in a **dedicated thread** (NFR-1 constrains
     MQTT callbacks only).
2. **Channel start pass** (`__start_direct_mount_channels`, dedicated
   thread, started from `__on_mqtt_connected`):
   - `pairs = self.__query_direct_mount_domains()` — `None` (query failed)
     ⇒ `warn` log, the component **stays `STARTING`** (no retry — NFR-3);
     `[]` ⇒ `READY` (nothing to start).
   - For each `(name, mode)`: **single non-blocking** domid read
     (`System().get_domain_domid(name)`, NFR-1 compliant — the old 60 s
     xenstore polling is gone). Dom0 registers the domids of every domain at
     domain creation, which precedes the guest openrc boot of sys-usb, so
     the domid is resolvable at this point; if it is not (edge case), the
     domain's channel is skipped with a `warn` log and the component still
     becomes `READY` (the other domains stay functional; the missing channel
     is visible in the controller log).
   - Each channel is started **as root, via doas**: the controller runs as
     `svc-sys-usb-controller`, but the per-session sandbox
     (`bwrap` → `setpriv` → `sftp-server`) needs a root parent to drop to
     `svc-sys-usb-sftp`. The call is
     `doas /usr/lib/safecor/bin/safecor-dm-channels.py <json-spec>` — a new
     thin root helper (package script) that imports the channel functions
     from the library and runs the `start-stop-daemon` sequence only. The
     doas permission is explicit and narrow (one script), mirroring the
     existing `doas /sbin/reboot` pattern.
   - When the pass completes: `__set_direct_mount_state(READY)`.
3. **Channel runtime files** (new dedicated directory, created by the
   controller initd as root, owned by the controller user):
   `/var/run/safecor/direct-mount/` — the UNIX socket
   `vchan-<name>.sock`, the pidfiles `socat-<name>.pid` /
   `vchan-<name>.pid` and the per-domain log `vchan-<name>.log`. The sandbox
   passwd moves there too (`sftp-sandbox-passwd`) — it is regenerated at
   every boot by the same component that needs it (the controller user
   cannot write the package directory `/usr/lib/safecor/etc`).
4. **Integrating the SFTP logic** (module-level, in
   `_sys_usb_controller.py`, adapted to `MountMode`):
   `SFTP_ROOT`, `SFTP_SERVER`, `MUSL_LOADER`, `SFTP_USER`,
   `SFTP_RUNTIME_DIR`, `SANDBOX_PASSWD`, `parse_direct_mount_domains`
   (returns `list[tuple[str, MountMode]]`), `sftp_server_args(MountMode)`,
   `sftp_credentials`, `parse_ldd_output`, `setpriv_library_paths`,
   `write_sandbox_passwd`, `bind_dirs`, `SandboxContext`, `bwrap_args`
   (`--ro-bind` for `MountMode.RO`), `sandbox_context`,
   `start_sftp_channel(name, domid, mode, uid, gid, ctx)`,
   `stop_sftp_channel(name)`. The values of `SFTP_ROOT` / `SFTP_SERVER` /
   `MUSL_LOADER` / `SFTP_USER` are unchanged.
5. **`OFF` on shutdown/reboot**: `__handle_restart` (for `sys-usb`) sets the
   state to `OFF`, publishes the three components `OFF`, stops the channels
   (doas helper, best-effort) and reboots. `stop()` does the same
   best-effort (no reboot).

## 5. DirectMountManager (business DomU side) — event-driven rewrite

Standalone process (openrc `direct-mount`), one persistent MQTT client for
the whole process life. All MQTT callbacks are fast state updates only
(NFR-1); the mount work runs in a **worker thread**; the sshfs death is
caught by a **watchdog thread** blocking on `Popen.wait()` (an event, not a
poll).

1. **One-shot `my_config` query** (on the persistent client, requested in
   the ready callback, `{"domain_name": <self>}`):
   - `MountMode` ⇒ `__mount_mode` set, `info` log
     "direct_mount enabled (mode=…)";
   - `False` ⇒ `info` log "direct_mount is not enabled for this domain",
     clean exit (the process terminates after unmounting — nothing to do);
   - `None` (no answer in 10 s) ⇒ `warning` log (one-shot timeout watcher
     thread), the process **stays alive**; when the `safecor_direct_mount`
     component becomes `READY` (Dom0 is therefore up), **one** event-triggered
     one-shot re-query is issued (bounded — not a retry loop).
2. **Subscribe** to `system/discover/components/response` + **one-shot**
   `discover_components` request in the ready callback (covers the
   subscribe-after-publish race both ways, without polling, without
   retained messages).
3. **Event-driven mount**: the `ComponentsHelper` state of
   `safecor_direct_mount` is updated on every notification; when it is
   `READY` and the mode is known and the mount is not active ⇒ the worker
   mounts. Log points on the **message channel** (via `Logger`, one-shot):
   - attempt ⇒ `info` ("attempting to mount /media/usb via sshfs")
   - success ⇒ `info` ("/media/usb mounted (mode=…)")
   - failure ⇒ `warning` (+ reason: script write, sshfs start, exit code)
4. **`OFF`** (sys-usb reboot) ⇒ unmount (terminate sshfs + `fusermount -u`),
   `info` log.
5. **Watchdog**: the sshfs process death ⇒ `warning` log
   ("the sshfs process terminated, remounting") + remount (only while
   running and the component is not `OFF`).
6. `stop()` (SIGTERM/SIGINT, openrc stop): terminate sshfs + unmount + stop
   the client, exit 0.

The vchan client script (`/usr/local/bin/vchan-sftp`, sshfs `ssh_command`)
is still generated at mount time; it resolves the sys-usb domid at runtime
(`xenstore-read`), so it survives domid changes. The `reconnect` sshfs
option is kept (heals a dropped session, complements the watchdog).

## 6. File-by-file changes

| File | Change |
|---|---|
| `python/lib/src/safecor/_constants.py` | + `MountMode` enum, + `Constants.SAFECOR_DIRECT_MOUNT` |
| `python/lib/src/safecor/__init__.py` | export `MountMode` |
| `python/lib/src/safecor/_sys_usb_controller.py` | SFTP channel logic integrated (module-level functions + `start_sftp_channel` / `stop_sftp_channel`), `safecor_direct_mount` component (state + `__publish_component_states`), one-shot `my_config` (event-signalled), channel thread, `OFF` on restart/stop |
| `python/lib/src/safecor/_direct_mount_manager.py` | event-driven rewrite (persistent client, `ComponentsHelper`, worker + watchdog threads, log points, unmount-on-OFF) |
| `setup/packages/safecor/safecor-sys-usb/safecor-dm-channels.py` | **new** — thin root helper (doas) running the `start-stop-daemon` sequence via the library functions |
| `setup/packages/safecor/safecor-sys-usb/safecor-vchan-sftp.py` | **deleted** |
| `setup/packages/safecor/safecor-sys-usb/safecor-vchan-sftp.initd` | **deleted** |
| `setup/packages/safecor/safecor-sys-usb/safecor-sys-usb-controller.initd` | create `/var/run/safecor/direct-mount/` (owned by the controller user) at start |
| `setup/packages/safecor/safecor-sys-usb/doas-svc-sys-usb-controller.conf` | + `permit nopass svc-sys-usb-controller as root cmd /usr/lib/safecor/bin/safecor-dm-channels.py` |
| `setup/packages/safecor/safecor-sys-usb/safecor-sys-usb.post-install` | stop + `rc-update del` the `safecor-vchan-sftp` service (upgrade path) |
| `setup/packages/safecor/safecor-sys-usb/APKBUILD` | source: −2 sftp files, + `safecor-dm-channels.py`; package(): same; sha512: remove the 2 sftp lines, recompute the 4 modified files (initd, doas conf, + the new helper) — no version bump |
| `python/lib/src/tests/test_direct_mount_manager.py` | rewritten for the event-driven design |
| `python/lib/src/tests/test_sys_usb_controller.py` | **new** — relocated SFTP pure-function tests (bwrap arg lists with the new passwd path, `parse_direct_mount_domains` with the enum) + component-state / channel-thread tests |
| `python/lib/src/tests/test_packages.py` | `TestSafecorVchanSftp` removed (its module is deleted; the tests live in `test_sys_usb_controller.py`) |
| `docs/specifications/features.md` | NFR-3 row (§11), component discovery note (§6) |
| `docs/specifications/python-api.md` | NFR-3 row, module map rows (`_sys_usb_controller.py`, `_direct_mount_manager.py`, `_constants.py`) |
| `docs/architecture/components/direct-usb-mount.md` | event-driven semantics, single sync point, doas helper, runtime dir |
| `docs/diagrams/lld-sftp-inputs.mmd` + inline block in the doc above | the SFTP server node is started by the `SysUsbController` (`safecor_direct_mount`), the socket path moves to the runtime dir |
| `docs/plans/direct-mount-event-driven.md` | this spec (part of the commit) |

`safecor-domu-base` (initd `direct-mount`, launcher
`start-direct-mount.py`): **unchanged** — they call `manager.run()`, whose
signature is preserved. `safecor-lib` copies the `python/lib` directory
whole (no per-file sha512).

## 7. Test plan

- `test_sys_usb_controller.py` (new):
  - the relocated SFTP pure functions: `parse_direct_mount_domains`
    (enum result, falsy disabled, invalid mode → `RW`, non-dict → `RW`,
    empty), `sftp_server_args` (enum), `sftp_credentials` (+ missing
    account), the exact `bwrap_args` lists for `RW`/`RO` (passwd under
    `/var/run/safecor/direct-mount/sftp-sandbox-passwd`),
    `parse_ldd_output` (3 cases), `setpriv_library_paths`, `bind_dirs`
    (2 cases), `write_sandbox_passwd`.
  - `__publish_component_states`: the payload contains the three components,
    `safecor_direct_mount` with its current state;
  - `__handle_discover_components` reports the current state (not a
    hardcoded READY);
  - `__on_mqtt_message` routes the `my_config` response to the waiter;
  - `__start_direct_mount_channels`: query failed ⇒ `STARTING` + warn; zero
    domains ⇒ `READY`; domid missing ⇒ channel skipped + warn, still
    `READY`; normal case ⇒ doas helper invoked per domain + `READY`;
  - `__handle_restart` (sys-usb): all three components published `OFF`,
    channels stopped, reboot invoked;
  - `stop()`: state `OFF`, channels stopped.
- `test_direct_mount_manager.py` (rewritten):
  - `__parse_mount_mode`: `RO`/`RW` enabled, invalid mode → `RW`, falsy
    `direct_mount` → `False`, domain absent → `None`;
  - `__on_message`: components notification updates the helper state and
    wakes the worker; `my_config` response sets the mode / exits cleanly on
    `False`; READY + mode unknown + no answer ⇒ one event-triggered
    re-query (bounded);
  - `__do_work`: `OFF` ⇒ unmount; `READY` + mode ⇒ mount attempt;
    `STARTING` ⇒ nothing;
  - watchdog: sshfs death ⇒ remount (event), no remount after `OFF`;
  - vchan script generation (unchanged content assertions);
  - sshfs options (`ro` for `MountMode.RO`, `reconnect` present);
  - `stop()` terminate/unmount behavior.
- `test_packages.py`: `TestSafecorVchanSftp` removed.
- Gates: `ruff format` + `ruff check` on every modified file; targeted
  pytest; full suite — the failing set must stay identical to the baseline
  (`/tmp/opencode/fail_base_ids.txt`, 22 pre-existing entries).

## 8. Risks / edge cases

- **Subscribe-after-publish race (DomU)**: covered by the subscribe +
  one-shot `discover_components` request (both orders of boot are handled,
  no polling, no retained message).
- **`my_config` one-shot failure (both sides)**: logged as `warning`; the
  DomU stays alive and re-queries **once** when the component is `READY`;
  sys-usb keeps the component `STARTING` (visible in the diagnostics). No
  retry loops (NFR-3).
- **Zero `direct_mount` domains**: the component is `READY` with no channels
  (nothing to start); the DomU that boots with `direct_mount=False` exits
  cleanly.
- **Missing domid at channel start** (edge): the domain's channel is
  skipped with a `warn` log; the component is still `READY` so the healthy
  domains mount; the missing channel is visible in the controller log.
  (Dom0 registers the domids at domain creation, which precedes the
  sys-usb guest openrc boot, so this should not occur in practice.)
- **Idempotency of the channel start**: `start_sftp_channel` stops the
  existing instances (pidfiles) and removes the stale socket before
  starting (behavior inherited from the run-15 fix).
- **NFR-1 compliance**: every MQTT callback only updates state / signals an
  event; the blocking work (my_config wait, sshfs spawn, `Popen.wait`) runs
  in dedicated threads.
- **Privilege drop**: the sandboxed `sftp-server` still runs as
  `svc-sys-usb-sftp` with no capabilities (setpriv from a root parent —
  hence the doas helper); the controller user is only granted the narrow
  `doas` permission on the channel helper.
- **Runtime dir on tmpfs**: `/var/run/safecor/direct-mount/` is recreated at
  every boot by the controller initd; the sandbox passwd is regenerated by
  the same boot, so the previous "persistent location" concern (commit
  `580dee7`) no longer applies — the file now lives with its consumer.
- **`safecor-vchan-sftp` on an upgraded system**: the post-install stops and
  removes the service; the `safecor-lib` and `safecor-sys-usb` packages must
  be reinstalled together (the controller calls the helper shipped by
  `safecor-sys-usb`).
