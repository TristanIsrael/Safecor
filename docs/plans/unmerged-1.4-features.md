# Unmerged 1.4 features — technical debt tracker

This document tracks the work that was coded on the **`1.4` line** (branch `origin/feature-212`) but was never merged into `main` or `version-2`. It is a technical debt inventory: each feature is described with its changes, its porting difficulty onto `version-2`, and a suggested approach. This debt will be handled **after the current operations are completed** (the channels → vchan migration, issue #256, runs 11/12).

## Branch state

| Property | Value |
|---|---|
| Branch | `origin/feature-212` (working name: `1.4`) |
| Branch tip | `e7c8b6c` (2026-11-18) |
| Merge base with `main` | `60963cf` (2026-07-02) |
| Commit date range | 2026-05-27 → 2026-11-18 |
| Commits ahead of `main` / `version-2` | 39 (same set for both) |
| Commits `version-2` has that the branch lacks | 201 (the whole v2 refactoring) |
| Changed files vs `main` | 78 files, +959 / −313 |
| Library version on the branch | 1.4.0 (`main` is 1.3.1) |

A direct merge is **not possible**: `version-2` heavily refactored the same files (vchan migration, new domain disk layout, apkovl provisioning, HVM fix) while the branch still carries pre-v2 code in some of them (e.g. its `create-domains.py` is the 9p-era version with `p9` shares and `/media/cdrom/apks`). The branch must be consumed **feature by feature**, ported onto `version-2`.

## Kanban status

All 16 related issues are in the **Safecor Kanban** project: 15 are **In review**, #207 is **Done**.

## Feature inventory

| Issue | Title | Type | Porting risk |
|---|---|---|---|
| #200 | Create a package with tools for debugging | feature, debugging | Low |
| #29 | Hide GRUB menu during the boot | feature, UX/UI | Low |
| #209 | NTFS disk without partition table not recognized | bug | Low |
| #210 | Avoid conflicts when 2 storages have the same name | feature | Low |
| #207 | Disk without name: new disk message not sent | bug (Done) | Low |
| #162 | sys-usb sends a component state notification before resetting | feature | Medium (incomplete on the branch) |
| #195 | Hide the mouse cursor when no mouse is connected | feature, UX/UI | Low–medium |
| #150 | Red root console in the Domains when in debug mode | UX/UI | Low–medium |
| #118 | Add syslog in sys-usb for system log | feature | Low–medium |
| #215 | Redirect all system logs to syslog | technical-debt | Medium |
| #185 | Chassis type key in the system information (tablet detection) | feature | Medium |
| #214 | Provide information about the storages | feature | Medium |
| #113 | Harden the mkimg.sh parameters (kernel) | security | Low (mostly already done in v2) |
| #212 | Apply the stateless rule to the whole system | feature, security, optimization | High |
| #168 | Encrypted storage in a file on the local disk | security | High |
| #18 | Reduce privileges in the storage (security) | security | High (with #212/#168) |

## Feature details

### #200 — `safecor-debug-tools` package (commits `cd7d585`, `ebc3f3b`)
New package `setup/packages/safecor/safecor-debug-tools/`: an `APKBUILD` (noarch) that depends on `pciutils htop iotop strace perf lstop ncdu evtest lsblk util-linux`, a post-install that logs a warning ("should not be installed on a production system"), and a marker file `/etc/.debug_tools`.
Porting: new files, no conflict with `version-2`.
**Open item (user request)**: the package is not part of the distribution, so DomUs cannot install it. It must be **integrated into `packages.squashfs` when the debug mode is active** (`DEBUG=ON` on the Dom0 kernel command line). The package has to be built and available to Dom0 first (published to the Safecor repository or dropped in the local repository), then fetched into `/usr/lib/safecor/packages` before the squashfs is built. Suggested hook: `create-local-alpine-repository.sh` (or `finish-core-init.sh`), guarded by `grep -q "DEBUG=ON" /proc/cmdline`, with `apk fetch -R safecor-debug-tools` + reindex/sign. This makes the tools installable in any DomU during a debug session.

### #29 — Hide the GRUB menu (commits `8f1fc84`, `4a5cd00`)
`grub.default`: `GRUB_TIMEOUT=1`, `GRUB_TIMEOUT_STYLE=hidden`, `gfxterm` disabled (`GRUB_TERMINAL_OUTPUT` emptied, `GRUB_TERMINAL_INPUT=console`).
Porting: single file. **Verified**: the `version-2` `grub.default` is identical to the pre-1.4 one (gfxterm still enabled, no `GRUB_TIMEOUT_STYLE`), so the change applies cleanly.

### #209 / #210 / #207 — USB storage detection and naming (commits `8ec075d`, `a865ea8`)
- `99-usbdisks.rules`: the `ENV{DEVTYPE}=="partition"` requirement was dropped, so a disk **without a partition table** (raw NTFS/exfat) is now recognized (#209).
- `mdev-usb-storage.sh`: full rewrite — unique mount point names (`.1`, `.2`, … suffixes) to avoid conflicts between two storages with the same name (#210), `NONAME` fallback for unlabeled disks so the new-disk message is sent (#207), hardened mount options (`noexec,nosuid,nodev`), and syslog logging via `logger` instead of a log file.
Porting: self-contained in `safecor-sys-usb`. **Verified against `version-2`**: the v2 `99-usbdisks.rules` is a *newer* GOTO-chain rule (it excludes the domain's own `xvd*` PV disks and requires `ID_BUS=="usb"`) that still keeps the `DEVTYPE=="partition"` requirement — the 1.4 rule must **not** be copied as-is; the partition requirement has to be dropped in the v2 rule while keeping its exclusions. The v2 `mdev-usb-storage.sh` is still the pre-1.4 version (file log, no unique names, no hardened options), so the 1.4 rewrite applies. #207 is already **Done** in the Kanban — close the loop after validation.

### #162 — Component state notification before reset (commit `6149b4e`)
New script `safecor-sys-usb/notify-controller-stopped.py`: when the sys-usb controller stops, it publishes a `DISCOVER_COMPONENTS` response with the disk controller and input controller in state `OFF`, so Dom0 knows the components are gone before any reset.
Porting: **incomplete on the 1.4 branch** — verified: `notify-controller-stopped.py` is not in the branch's `safecor-sys-usb` APKBUILD `source` list and nothing references it; the script was written but never packaged or wired. The port must complete the feature: add the script to the APKBUILD (source + sha512), and call it (with a timeout) from the `stop()` of `safecor-sys-usb-controller.initd` before the controller is killed — the v2 `stop()` is currently a plain `kill -9` with no notification hook. **Verified**: `ResponseFactory.create_entry_component_state` and `create_response_component_state` already exist in the v2 lib, so the script works unchanged.

### #195 — Hide the mouse cursor when no mouse is connected (commit `edcd613`)
`safecor-gui-base`: `unclutter-xfixes` added to `depends`; `configure-x.sh` starts `unclutter-xfixes -idle 1 -root -noevents &`.
Porting: **verified** — the `version-2` `configure-x.sh` is still the pre-1.4 version (plain `echo`, no unclutter), so the unclutter line and the `depends` entry apply cleanly. Note the v2 GUI domain now uses `vga = "stdvga"` (see #256 run 11 fix), which does not affect this feature.

### #150 — Red root console in debug mode (commit `9031811`)
New `safecor-domu-base` files: `/etc/profile.d/color_prompt.sh` (red prompt + `#` for root/sudo, green + `$` for regular users, bash and zsh) and `/etc/motd` (banner: "Safecor Domain debugging console — changes will be lost on reboot, this console is only for debugging"). The `version-2` domu-base APKBUILD currently has `source=""` (verified), so adding these files requires extending the source list with sha512 checksums.
Porting: new files plus APKBUILD install rules. Note: on the 1.4 branch this commit also removed the `installed` marker line from the package function — do not regress the v2 behavior.

### #118 — syslog in sys-usb (commit `c78a0cd`)
Sys-usb scripts switched from `echo`/file logs to `logger` (syslog): `mdev-usb-storage.sh`, `hardening.sh`, `safecor-sys-usb.post-install`, `safecor-sys-usb-controller.py`; small tweak in `safecor-logger-daemon.py` and the syslog Readme.
**Verified gap in `version-2`**: the 1.4 branch made `safecor-domu-base` depend on `safecor-syslog` (and `safecor-hardening`), but the v2 `safecor-domu-base` depends on neither — and no other package in the v2 core chain installs `safecor-syslog` into a DomU (the apkovl world only carries the domain's main package). The port must make an explicit decision: restore the 1.4 approach (domu-base pulls `safecor-syslog` + `safecor-hardening`) or install it per-domain in the topology. The v2 logging chain is rsyslog `omuxsock` → `safecor-logger-daemon.py` → MQTT `system/events/*` over the vchan msg channel, so `logger` calls from sys-usb scripts will flow correctly once the package is present.

### #215 — Redirect all system logs to syslog (commits `742080e`, `08ca1e7`)
`logger` calls added across the core scripts (`create-tty-terminal.sh`, `create-tty-tunnel.sh`, `create-swapdisk.sh`, `orchestrator.py`), the domu-base post-install, and the gui-base scripts (`configure-x.sh`, `hardening.sh`, `xserver.initd`, post-install); duplicated work removed from `safecor-core.post-install`.
Porting: medium — the `version-2` versions of those scripts changed with the vchan migration; re-apply the logging calls on the v2 scripts. Handle together with #118 (same scripts, same goal).

### #185 — Chassis type in the system information (commit `629e874`)
Library changes: new `ChassisType` enum (`unknown`/`desktop`/`laptop`/`tablet`), `System.get_dmi_chassis_type()` reading `/sys/class/dmi/id/chassis_type`, `System.decode_dmi_chassis_type()` (DMI code mapping: 30 = tablet, …), and a new `machine.chassis` key in the system information payload. Unit tests added in `test_system.py`.
Porting: `_system.py` was refactored in `version-2`; re-apply the additions.

### #214 — Storage information (commits `19f683e`, `ebbbbc66`)
New MQTT command `disks/storage_info` (`Topics.STORAGE_INFO`): `Api.request_storage_info(disk)` in the DomU side; `Dom0Controller` answers for the local storage (`STR_REPOSITORY`) and `SysUsbController` answers for USB disks; the response carries `total`/`used`/`free` from `shutil.disk_usage`. New `RequestFactory.create_request_storage_info` / `ResponseFactory.create_response_storage_info`, and `FileHelper.get_mount_point` special-cases the repository.
Porting: additive library changes, but the v2 lib refactored the touched files — re-apply and add unit tests.

### #113 — Harden the mkimg.sh parameters (commits `b414a25`, `bda3b96`)
`setup/iso`: `mkimg.safecor.sh` and `genapkovl-safecor.sh` moved into a new `setup/iso/template/` directory; `mkimg.tests.sh` gains a `profile_diag` (diagnostic ISO profile with a hardened kernel cmdline: `console=null loglevel=0 autodetect_serial=no`); `genapkovl-diag.sh` drops the `xen_netback` module; `sys-gui` removed from the GitHub Actions workflow.
Porting: **verified — mostly already done in `version-2`**: the diag ISO (`setup/iso/diag/mkimg.diag.sh`) already carries the hardened kernel cmdline (`console=null loglevel=0 autodetect_serial=no`, lts flavor) and `sys-gui` is no longer in the v2 CI workflow. Only the `xen_netback` removal from `genapkovl-diag.sh` (still present in v2, line 36) remains. The 1.4 `template/` reorganization and the `profile_diag` in `mkimg.tests.sh` are obsolete (the v2 virt ISO is built by `safecor-virt/mkimg.safecor-virt.sh`) and should not be ported.

### #212 / #168 / #18 — Local storage stack (stateless + encrypted + hardened) (commits `1ea8a3f`, `9661d05`, `a576e39`, `6026524`, `c62211a`, `a391d0d`, `e9fe804`, `80564a1`, `535a63f`)
The biggest and most coupled group:
- **Topology** (#212): new `system.storage` keys in the topology (`on_disk`, `index`, `size`) parsed in `_system.py` (load, defaults, `to_struct`), test fixtures updated.
- **Orchestrator** (#212/#18/#168): at boot, if `storage.on_disk` the orchestrator runs `doas create-encrypted-storage.sh <index> <size>`, otherwise `doas create-memory-storage.sh`.
- **`create-encrypted-storage.sh`** (#168, new, 103 lines): selects the n-th physical disk, `wipefs` + `sfdisk` GPT + `mkfs.ext4 -L Safecor`, generates a random 512-bit key in `/dev/shm/keys`, creates a **LUKS2** container `storage.img` (1000 PBKDF2 iterations — justified because the key is random), loop-mounts it, `mkfs.ext4`, and mounts at `/usr/lib/safecor/storage` with `noexec,nosuid,nodev`. Permissions: `root:safecor 660` on the image, `svc-safecor-controller:safecor 2770` on the mount.
- **`create-memory-storage.sh`** (#18/#212, new): mounts a hardened `tmpfs` (`noexec,nosuid,nodev`) at `/usr/lib/safecor/storage`.
- **`clean.initd`** (#212, new): the service's `stop()` deletes `/media/*/storage.img` — the stateless rule: the local storage is wiped on shutdown.
Porting: **high risk** — the branch's `orchestrator.py` and `create-domains.py` are pre-v2 (the branch even comments out `__fetch_alpine_packages` and points the 9p share at `/media/cdrom/apks`; **do not port those parts**). Only the storage logic (topology keys, scripts, orchestrator hook, clean.initd) is to be re-applied onto the v2 orchestrator. **Verified**: the v2 `_system.py` topology loading (system keys around lines 288-299, defaults around line 377) is the natural insertion point for the `storage` keys; v2 also carries newer keys the branch lacks (`repository_disabled`), so the port is additive but must not regress them. Security review recommended on reintegration (key in `/dev/shm`, low PBKDF2 iteration count, `losetup /dev/loop1` hardcoding).

## Housekeeping commits (no feature content)

| Commit | Content |
|---|---|
| `b6547c2` | Update `_constants.py` (minor) |
| `4dd252a`, `ff9accd`, `e0ebe23`, `70ebabe` | APKBUILD version bumps (lib 1.4.0, hardening 1.2 → 1.3, others) |
| `faa3ea1` | Update checksums |
| `bb9ff48`, `9d5467c` | Readme / doc updates |
| `bda3b96` | Removed sys-gui from GitHub Actions |
| `f013163` | "Changed hardening": hardening moved out of the core `hardening.initd` into the `safecor-hardening` package (new `hardening.initd` there, `safecor-hardening` 1.3, domu-base post-install starts the service, core initd simplified) |
| `88361a8`, `0b967b4` | Merge commits (local branch `1.4`) |
| `92d7544`, `e7c8b6c` | `.gitignore` / `Safecor.code-workspace` (2026-11-18) |

Note: `f013163` (hardening package rework) is feature-adjacent and should be evaluated together with #150/#215/#118 when the v2 hardening flow is reviewed.

## Other unmerged branches (minor)

| Branch | Ahead of `main` | Content |
|---|---|---|
| `origin/feature-241` | 2 merge commits only | **No real debt**: the merged work (fixes 242-243-244) is already in `main` (0 non-merge commits ahead). |
| `origin/fix/sphinx-doc-build` | 1 commit | `850b0ea` — Fix the documentation Pages deployment (poetry is not on the runner). |
| `origin/refactor` | 1 commit | `65a9775` — docs: apply point-by-point review corrections to features reference. |

## Other observations made during the audit

- `setup/packages/safecor/safecor-tests/topology.json` is still in the **v1.3 topology format** (`business.domains` / `app-package`), which the v2 `Topology` loader does not parse. The test appliance needs its topology regenerated for v2 — a separate item from this debt, to be raised on its own issue.
- The 1.4 branch bumped the library to **1.4.0** while `version-2` still carries the v2 versioning under refactoring — the final versioning decision stays with the maintainer (see versioning rules in `AGENTS.md`).
- The branch name on GitHub is `feature-212` but the work covers 16 issues; its local working name was `1.4` (visible in its merge commit messages).

## Suggested approach (once the current operations are done)

1. **Never merge the branch.** Port feature by feature onto `version-2` on dedicated branches, following the project rules (one branch/commit per issue, Kanban update, unit tests, sha512 recalculation).
2. **Suggested order** (low risk → high risk, updated after the audit):
   1. #200 — `safecor-debug-tools` + the `packages.squashfs` integration when `DEBUG=ON` (user request)
   2. #29 — GRUB menu
   3. #113 — ISO hardening (reduced to the `xen_netback` removal, verified)
   4. #209 / #210 / #207 — USB storage detection and naming (merge the 1.4 rule changes into the v2 GOTO-chain rule)
   5. #162 — controller stop notification (**complete the missing packaging and stop-hook wiring**)
   6. #195 — mouse cursor
   7. #150 — red root console
   8. #118 + #215 — syslog redirection (together, same scripts) + the `f013163` hardening rework evaluation + the decision on making `safecor-domu-base` depend on `safecor-syslog` / `safecor-hardening`
   9. #185 — chassis type
   10. #214 — storage information
   11. #212 + #168 + #18 — the local storage stack (together, high risk, security review)
3. **After the porting**: archive/delete `feature-212`, reconcile the library version (the branch carries 1.4.0; the `version-2` versioning stays under the maintainer's versioning rules), and pick up the two minor branches (`fix/sphinx-doc-build`, `refactor`) if still relevant.
4. **Per-feature validation** on the test machine (run 13+): each ported feature gets a verification entry in the test plan, in line with the existing run-based process.
