# Safecor — Code ↔ Documentation Synchronization Issues

> **Status**: Working list (to be addressed later)
>
> **Last updated**: 2026-11-01
>
> **Purpose**: catalogue of every mismatch found while cross-referencing the **Safecor Wiki**
> (public documentation, `Safecor.wiki/`) against the **code** (`python/lib/src/safecor/`).
> Each entry records the discrepancy, which side is authoritative, the related existing GitHub
> issue (when one exists), and the suggested fix. **Nothing here is fixed yet** — this file is
> the input for follow-up work.
>
> **Companion docs**: [`docs/architecture.md`](architecture.md), [`docs/features.md`](features.md).

**Legend (authoritative side)**:
- **CODE** — the code is correct; the Wiki must be corrected.
- **DOC** — the Wiki states the intended contract; the code deviates (a code bug / gap).
- **BOTH** — code and Wiki disagree with each other *and* with the intended design; needs a
  decision on the canonical contract.

---

## 1. Protocol field & topic mismatches (Wiki `Protocol.md` vs code)

| ID | Function | Wiki says | Code says | Authoritative | Related issue | Suggested fix |
|----|----------|-----------|-----------|---------------|---------------|---------------|
| P1 | File fingerprint — **topic** | `system/disks/file_footprint/{request,response}` | `system/disks/file_fingerprint/…` (`_topics.py:26` `FILE_FINGERPRINT`) | **CODE** | #219 | Rename the Wiki topic to `file_fingerprint` |
| P2 | File fingerprint — **response field** | `footprint` | `fingerprint` (`_response_factory.py:61` `create_response_file_fingerprint`) | **CODE** | #219 | Rename the Wiki field to `fingerprint` |
| P3 | New file notification — **fingerprint fields** | `source_footprint` / `dest_footprint` | `source_fingerprint` / `dest_fingerprint` (`_notification_factory.py` `create_notification_new_file`) | **CODE** | #219 | Rename the Wiki fields to `*_fingerprint` |
| P4 | List files — **request field** | `name_filter` (list) | `name_filters` (`_request_factory.py:50` `create_request_files_list`) | **CODE** | (see also bug #218) | Rename the Wiki field to `name_filters` |
| P5 | Switch GUI — **request field** | `{ "domain_name": … }` | `{ "domain": … }` (`_request_factory.py:207` `create_request_switch_gui`; read as `payload.get("domain")` in `_dom0_controller.py:385`) | **CODE** | #222 | Rename the Wiki field to `domain` |
| P6 | System info — **storage field** | `storage.files_count` | `storage.files` (`_system.py:694` `__get_storage_info`) | **CODE** | #222 | Rename the Wiki field to `files` |
| P7 | Create file — **response undocumented** | "Response: *see New file notification*" (no response payload) | publishes `disks/create_file/response` = `{filepath, disk, fingerprint, success}` (`_response_factory.py:70` `create_response_create_file`) | **CODE** | — | Document the `create_file/response` payload in the Wiki |

## 2. Functions documented in the Wiki but NOT implemented in the code

| ID | Function | Wiki page | Code status | Related issue | Note |
|----|----------|-----------|-------------|---------------|------|
| U1 | **Storage info** (`system/disks/storage_info/{request,response}`) | `Protocol.md` "Request information about a disk" | ❌ No such topic in `Topics`; no handler | #220 | Documented capacity query is not implemented |
| U2 | **Monitoring** (`system/monitoring/{request,response}`) | `Protocol.md` "Monitoring", `Capabilities.md` | ❌ No such topic in `Topics`; no handler | #220, #227 | Documented domain monitoring is not implemented |
| U3 | **Monitoring capability** | `Capabilities.md` "Monitoring (since v1.0)" | ❌ unimplemented | #227 | Capability listed as shipped but absent |
| U4 | **Resource attribution** | `Capabilities.md` ("*cf topology*") | placeholder, no content | #227 | Section is a stub |

## 3. Code-internal bug surfaced by the doc comparison

| ID | Function | Detail | Authoritative | Related issue | Suggested fix |
|----|----------|---------|---------------|---------------|---------------|
| B1 | **Language list request never processed** | Three-way inconsistency on the list-languages topic. Intended contract (per `_topics.py` `LIST_LANGUAGES = settings/languages/list` and the Dom0 handler `_dom0_controller.py:323` `topic.startswith(Topics.LIST_LANGUAGES)`) is `system/settings/languages/list/request`. But `Api.get_languages_list()` (`_api.py:621`) publishes to `system/settings/languages/request`, **and** the Wiki also documents `system/settings/languages/request`. So the Api and the Wiki both deviate from the Dom0 handler → list requests are dropped. | **CODE (Dom0 handler + `Topics`)** | #217 | Make `Api.get_languages_list()` publish to `f"{Topics.LIST_LANGUAGES}/request"`; correct the Wiki topic to `…/languages/list/request` |

## 4. Topology key-name mismatches (Wiki `Topology.md` vs code)

The Wiki's **tables** disagree with both the Wiki's **own example** and the code
(`_system.py` `__analyse_topology_struct` / `__parse_topology`).

| ID | Section | Wiki table key | Code / example key | Authoritative | Related issue | Suggested fix |
|----|---------|----------------|--------------------|---------------|---------------|---------------|
| T1 | `screen` | `enable` (int) | `enabled` (`_system.py` reads `screen.get("enabled")`; example uses `enabled: 1`) | **CODE** | #226 | Rename the Wiki table key to `enabled` |
| T2 | `business.domains[].package` | `package` | `app-package` (`_system.py` reads `domain.get("app-package")`; example uses `app-package`) | **CODE** | #226 | Rename the Wiki table key to `app-package` |
| T3 | `business.domains[].temp disk` | `temp_disk` | `temp_disk_size` (`_system.py` reads `domain.get("temp_disk_size")`; example uses `temp_disk_size`) | **CODE** | #226 | Rename the Wiki table key to `temp_disk_size` |
| T4 | `storage` section | documented (`type`/`index`/`size`) + in example | **not parsed** by `System.__analyse_topology_struct` (only `usb`/`screen`/`vcpu`/`business`/`pci` are read) | **BOTH / needs decision** | — | Confirm whether the core orchestrator (non-Python) consumes `storage`; if the Python topology struct should expose it, add it; otherwise clarify in the Wiki that it is orchestrator-side only |

## 5. Obsolete / outdated Wiki pages

| ID | Page | Problem | Related issue | Suggested fix |
|----|------|---------|---------------|---------------|
| O1 | `Python-api.md` | Marked **"/!\ Obsolete"**, references the old **Panoptiscan** architecture (`panoptiscan_lib`, `/var/run/panoptiscan/*-msg.sock`, `/etc/panoptiscan/global.conf`) | #223 | Rewrite against the current `safecor` `Api` (or remove) |
| O2 | `Safecor-core.md` | Empty sections (`finish-core-init.sh`, `orchestrator.py`, `start-safecor-core-controller.py`) and a stale scripts/services list | #224 | Complete the empty sections; re-verify the scripts/services tables against the `safecor-core` package |
| O3 | `Emulator.md` | Accurate, but the **scenario API** coverage is partial (mentions `attach_disk`/`inject_key` only; omits `power_off`/`power_on`/`set_energy_state`/`set_default_language`/`restart_domain`) | — | Extend the scenario-API section when the operator console lands |

## 6. Minor / wording

| ID | Item | Detail | Suggested fix |
|----|------|--------|---------------|
| M1 | `create_file` compression | Wiki says binary data "compressed using the *GNU zip* algorithm"; the code uses `zlib` (deflate) (`_api.py` `create_file`, `zlib.compress`) | Correct the Wiki to "zlib/deflate" |
| M2 | Component state type | `Protocol.md` "Discover the components" says `state` is `(int)`; `ComponentState` values are **strings** (`ready`, `error`, …) | Correct the Wiki type to `str` |

---

## 7. Cross-reference with open GitHub issues

Issues already tracking part of this list (Safecor repo):

| Issue | Covers |
|-------|--------|
| #217 | B1 (language settings broken) |
| #218 | P4 (list_files name filter) — note #218 is about the filter being *silently ignored at runtime*, distinct from the doc field name |
| #219 | P1, P2, P3 (file fingerprint topic + fields) |
| #220 | U1, U2 (storage_info + monitoring documented but not implemented) |
| #222 | P5, P6 (switch_gui field, system_info storage field) |
| #223 | O1 (Python-api obsolete) |
| #224 | O2 (Safecor-core outdated) |
| #226 | T1, T2, T3 (topology table key names) |
| #227 | U3, U4 (Monitoring capability + Resource attribution placeholder) |

**New items not yet covered by an open issue** (candidates for new issues): P7, T4, O3, M1, M2.

## 8. Impact on the emulator operator-console work

- **B1 / #217** is directly relevant: the operator console's **language** control (Phase 0/1 of
  `plans/emulator-plan.md`) drives the language settings. If the language list/set path is broken,
  the console's language feature cannot be validated end-to-end. Decide whether to fix #217 as
  part of the emulator work or treat it as a separate prerequisite.
- **U1/U2** (storage_info, monitoring) are **not** in the current emulator scope; they remain
  out of scope unless the operator selects them.
- The **topology** decision (T1–T4) reinforces the need to serve + parse `topology.json` in the
  console using the **code's** key names (`enabled`, `app-package`, `temp_disk_size`), not the
  Wiki's table names.
