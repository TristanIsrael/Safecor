# Run 21

Dedicated hardware validation of the **XenStore class integration** (#275, mechanism level) — kept separate from the end-to-end self-heal scenarios of [run 20](run-20.md).

The fix under test (on `version-2`, **not yet pushed**):

- **#275 (XenStore mechanism)** — every xenstore access in the library and in the Dom0 vchan tunnel manager now goes through the `safecor` library's **`XenStore` class** (Xen Python bindings over libxenstore, i.e. `xs_open(0)` + the `/dev/xen/xenbus` device): no `xenstore-read`/`xenstore-write`/`xenstore-ls` subprocesses are spawned anywhere, and the `doas` grant `conf/doas-svc-vchan-tunnels.conf` is **removed** (the `svc-vchan-tunnels` user already has read/write on the `/local/domain/system` subtree through `set-xenstore-permissions.sh`).

Purpose: prove that the XenStore integration works end-to-end on the appliance (Dom0 + DomUs) — the bindings open the device, the per-domain grants are sufficient, and each migrated call site returns the right values — **before** relying on it in the run-20 end-to-end scenarios.

Preparation:
- [ ] Rebuild **`safecor-lib`** and **`safecor-core`** from the `version-2` tip (no version bump). `safecor-lib` carries the `XenStore` class and the migrated call sites; `safecor-core` carries `create-vchan-tunnels.py` (rewritten, recalculated sha512) **without** the doas conf.
- [ ] Install `safecor-lib` on **Dom0**, **sys-usb** and the business DomUs (version consistency); install `safecor-core` on **Dom0**.
- [ ] **Restart the running `sys-usb` controller** (`/etc/init.d/…` or `kill` + openrc respawn) so it picks up the new domid-read path — a running process keeps the old code until restarted.
- [ ] Full cold reboot in debug mode with a USB disk connected before boot.

## 1. The XenStore bindings open the device (both sides)

- [ ] On Dom0: `ls -l /dev/xen/xenbus` → `crw-r----- root safecor` (640) (the xenstore access node, group `safecor`).
- [ ] On Dom0, as a `safecor`-group user: `python3 -c "from safecor import XenStore; xs=XenStore(); print(xs.read_path('/local/domain/0/domid'))"` → prints `0`.
- [ ] On **sys-usb**: same one-liner → `0` (Dom0's domid is readable in the shared tree) — proves the DomU→xenbus path works for a non-root service user.
- [ ] On **sys-usb**: `python3 -c "from safecor import XenStore; xs=XenStore(); print(xs.read('system','domids/sys-usb'))"` → the sys-usb domid (matches `xl domid sys-usb` on Dom0).

## 2. No CLI subprocesses, no doas (attack surface)

- [ ] On Dom0: `ls /etc/doas.d/` → **no** `svc-vchan-tunnels.conf` (the other confs — `svc-orchestrator`, `svc-safecor-controller` — are still there).
- [ ] With all channels running: `ps ax -o user,args | grep -E "xenstore-(read|write|ls)" | grep -v grep` → **no process** (nothing in the migrated flow spawns the CLI; `reboot-domain.sh` is not running at idle).
- [ ] `create-vchan-tunnels` service is `up` (openrc status) and its discovery loop is running (log line `vchan-tunnels: starting discovery loop` on boot, no error loop).

## 3. Migrated call sites return the right values

- [ ] On a DomU (e.g. sys-usb): `python3 -c "from safecor import System; s=System(); print(s.get_screen_width(), s.get_screen_height(), s.get_screen_rotation())"` → the product geometry (matches the run-20 §1 baseline; no `0 0 0` fallback).
- [ ] On Dom0: `python3 -c "from safecor import System; print(System().get_current_domid())"` → `0`.
- [ ] On **sys-usb**: the direct-mount channels start on their own (run-20 §1 probe) — the controller resolved the domids through `XenStore().read("system", "domids/<name>")` (the migrated `__read_cached_domid`), not the removed `System.get_domain_domid`.
- [ ] `python3 -c "import safecor; print(hasattr(safecor, 'XenStore'), hasattr(safecor.System, 'get_domain_domid'))"` on Dom0 and sys-usb → `True False` (class exported, old method gone).

## 4. The discovery loop self-heals through XenStore (mechanism cross-check)

- [ ] On Dom0, for each domain `<name>`: `xl domid <name>` equals `xenstore-read /local/domain/system/domids/<name>` (the cache is consistent at boot — same check as run-20 §1, expected via the new code path).
- [ ] Restart **sys-usb** via the API (non-forced). Within a few seconds on Dom0: the `create-vchan-tunnels` log shows `domid <old> -> <new> (self-heal for sys-usb)`, the cache now equals `xl domid sys-usb`, and the three vchan servers (msg/input/tty) are re-pinned on the **new** domid.
- [ ] No `doas`/permission error for `svc-vchan-tunnels` in the logs around the self-heal (the write-back is a plain `XenStore.write` over the already-granted subtree).

## 5. Verdict

- [ ] All of §1–§4 green → the XenStore integration is validated; run 20's end-to-end scenarios (OFF path, business reboot, Saphir simultaneous reboot) can rely on it.
- [ ] Any failure → record the probe output, the failing call site and the log lines; the mechanism is not validated (run 20 must not be started on top of it).
