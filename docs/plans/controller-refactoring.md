# Safecor Controller Refactoring Plan

> **Status**: Draft — analysis phase (quick fix pending)
>
> **Last updated**: 2026-11-05
>
> **Trigger**: Saphir Run 11 — target disk disconnection during copy was not
> rejected by the emulator; the state machine allowed report generation on a
> disconnected disk.
>
> **References**:
> - [`docs/architecture.md`](../architecture.md) §5 (emulatable surface), §6 (emulator)
> - [`docs/plans/emulator-plan.md`](emulator-plan.md) (operator console)
> - `Saphir/docs/plans/validation-tests.md` (Run 11 report)

---

## 1. Problem Statement

### 1.1 The divergence bug (Run 11)

During the copy phase, the target disk is disconnected. The real
`SysUsbController` would reject in-flight `COPY_FILE` and `CREATE_FILE`
requests (the disk is gone). The emulator's `MockSysUsbController` accepts
them because it never checks whether the referenced disk is still connected.

Consequences:
- Saphir's `TransferController` counts all files as copied → `transferComplete`
- The state machine transitions to `GeneratingReport`
- `CREATE_FILE` (report + journal) is accepted by the emulator
- The system reaches `SystemMustBeReset` with files "copied" to a nonexistent disk

### 1.2 Root cause

The mock is a **parallel implementation**: it re-implements the MQTT protocol
handling independently of the real controller. There is no shared code for the
protocol logic — only shared utilities (`ResponseFactory`, `Topics`,
`MqttHelper`). When the real controller validates a precondition (disk
connected), the mock doesn't, because the validation is not in a shared layer.

This is a **structural** problem, not a one-off bug. Every new precondition
added to the real controller will silently diverge from the mock until someone
notices.

---

## 2. Current Architecture

### 2.1 Real controllers

| Controller | File | Threading | Hardware coupling |
|---|---|---|---|
| `SysUsbController` | `python/lib/src/safecor/_sys_usb_controller.py` | Persistent worker threads + queues (`__copy_files_queue`, `__read_files_queue`) | `DiskMonitor` (inotify/pyudev), USB mount points, `FileHelper.copy_file` (subprocess `cp`) |
| `Dom0Controller` | `python/lib/src/safecor/_dom0_controller.py` | Per-message thread | `poweroff`, `reboot-domain.sh`, `XcbController` |

Key characteristics:
- **No base class**, no ABC, no inheritance hierarchy
- All handler methods are **name-mangled** (`__handle_copy_file`) → non-overridable
- Protocol handling (MQTT routing, payload validation, response formatting) is
  **interleaved** with hardware-specific operations in the same method

### 2.2 Mock controllers (emulator)

| Mock | File | Threading | I/O |
|---|---|---|---|
| `MockSysUsbController` | `python/emulator/src/safecor_emulator/peers/mock_sys_usb.py` | `ThreadPoolExecutor(max_workers=1)` | Local directories, `shutil.copy` |
| `MockDom0Controller` | `python/emulator/src/safecor_emulator/peers/mock_dom0.py` | `ThreadPoolExecutor(max_workers=1)` | Local directories, configurable properties |

Key characteristics:
- **No inheritance** from the real controllers
- Re-implement the same MQTT topics with the same `ResponseFactory` /
  `NotificationFactory` calls
- Add capabilities the real controllers don't have: `attach_disk()` /
  `detach_disk()` (hot-plug simulation), `EventBus` (test observation)

### 2.3 Shared code (the only coupling)

`MqttClient`, `Topics`, `ResponseFactory`, `NotificationFactory`, `Constants`,
`FileHelper`, `MqttHelper`, `DiskState`, `ComponentState`.

### 2.4 The implicit contract

The **MQTT protocol** (topic names, payload schemas, response formats) is the
only contract between real and mock. There is no code-level interface, no
shared base class, no protocol-level test that verifies the mock behaves like
the real controller.

---

## 3. Approach Comparison

### 3.1 Parallel mocks (current)

**Advantages:**
- Zero risk to production controller code
- Simpler: no need to untangle hardware from protocol
- Can add capabilities not in the real controller (hot-plug, EventBus)
- Fast to implement for new topics (just add a handler)

**Disadvantages:**
- **Behavioral divergence** — the root cause of the Run 11 bug
- Duplicated protocol logic (payload validation, response formatting, error handling)
- New preconditions in the real controller must be **manually replicated**
- No automated way to detect divergence
- Scales poorly: with N topics × 2 controllers, the surface area for divergence grows

### 3.2 Override / shared base (target)

**Advantages:**
- Protocol handling (routing, validation, response formatting, **precondition checks**) is in one place
- Mocks only specialize the I/O operations → minimal surface for divergence
- New preconditions added to the base are **inherited** by the mock
- Enables protocol-level conformance tests (the mock must pass the same tests as the real controller)

**Disadvantages:**
- Requires refactoring production controllers (rename mangled methods, extract base)
- Threading models differ (mock: `ThreadPoolExecutor`, real: persistent workers + queues) — the base must abstract this
- Higher initial effort
- Risk of regression in production controllers during refactoring
- The mock's unique capabilities (hot-plug, EventBus) must be layered on top of the base

### 3.3 When each approach is valid

| Stage | Approach | Rationale |
|---|---|---|
| Protocol still evolving | Parallel | Fast iteration, no risk to prod, mock can diverge intentionally (e.g., simulate errors the real HW wouldn't produce) |
| Protocol stable, E2E testing begins | **Transition** | The mock must now be **faithful** — divergence is a bug, not a feature |
| Production, recurring product integration | Override | Behavioral fidelity is a requirement, not a nice-to-have |

**Current stage**: Saphir validation (Runs 1–11) has exposed multiple
divergence bugs. The protocol is stable (no new topics in the last 3 months).
We are at the **transition** point.

---

## 4. End-to-End Testing Requirements

### 4.1 The need

The emulator must **qualify** Safecor's behavior in the context of a real
product (Saphir). This means:

1. The mock must **faithfully reproduce** the real controller's behavior,
   including error handling for edge cases (disk disconnection, missing disk,
   full disk, permission errors).
2. The product's test suite (Saphir) must be able to **drive** the emulator
   through complete scenarios (boot → analysis → copy → report → reset) and
   verify the product's state machine at each step.
3. **Divergence detection**: there must be an automated way to detect when
   the mock's behavior differs from the real controller's (at least for the
   protocol-level responses).

### 4.2 Key E2E scenarios (from Saphir validation)

| # | Scenario | Expected behavior | Current mock behavior |
|---|---|---|---|
| 1 | Copy in progress → target disconnected | `COPY_FILE` → error response; copy paused; no report | `COPY_FILE` → ok (BUG) |
| 2 | Copy in progress → source disconnected | `COPY_FILE` → error response; copy paused | Partially handled |
| 3 | Report generation → target disconnected | `CREATE_FILE` → error response; `SystemMustBeReset` | `CREATE_FILE` → ok (BUG) |
| 4 | Copy paused → same disk reconnected | Coherence check → resume | Handled |
| 5 | Copy paused → different disk reconnected | Coherence check fails → `SystemMustBeReset` | Handled |
| 6 | `list_files` on disconnected disk | Error / empty response | Handled (disk not in list) |
| 7 | `copy_file` from disconnected source | Error response | Handled (disk not in list) |
| 8 | `create_file` on disconnected disk | Error response (`success=False`) | Not handled (BUG) |

### 4.3 Fidelity criteria

The mock is **faithful** when, for every MQTT request:
- The **response schema** matches (same fields, same types)
- The **response values** match for the same preconditions (e.g., disk connected → ok, disk disconnected → error)
- The **error notifications** match (same topic, same payload structure)
- **Documented differences** are acceptable (e.g., the mock doesn't actually
  copy at USB speed; the mock supports hot-plug which the real controller
  handles via hardware events)

### 4.4 Divergence detection (future)

A **protocol conformance test suite** that:
1. Sends a fixed set of MQTT requests to both the real controller and the mock
2. Compares the responses (schema + values)
3. Fails if there is a mismatch

This would be the ultimate guard against divergence. It requires the
override architecture (or at least a shared test harness).

---

## 5. Target Architecture (Override)

### 5.1 Base class

```
python/lib/src/safecor/
├── _base_disk_controller.py    # NEW: BaseDiskController
```

`BaseDiskController` owns:
- MQTT subscription and message routing
- Payload validation (`MqttHelper.check_payload`)
- **Precondition checks** (disk connected? disk exists?)
- Response formatting (`ResponseFactory`)
- Error notification formatting (`NotificationFactory`)
- Abstract methods for I/O operations

Virtual methods (single underscore, overridable):

| Method | Purpose |
|---|---|
| `_get_connected_disks() -> list[str]` | List of connected disk IDs |
| `_get_disk_path(disk_id: str) -> str` | Mount path for a disk |
| `_perform_copy(source_path, dest_path) -> bool` | Actual file copy |
| `_perform_create(path, data) -> bool` | Actual file creation |
| `_perform_read(path) -> bytes` | Actual file read |
| `_perform_list(disk_id, recursive, from_dir) -> list[dict]` | Actual file listing |
| `_on_disk_connected(disk_id) -> None` | Hook for disk attach |
| `_on_disk_disconnected(disk_id) -> None` | Hook for disk detach |

The base class handles the full request lifecycle:
1. Receive MQTT message
2. Validate payload
3. **Check preconditions** (disk connected, etc.)
4. Call the virtual I/O method
5. Format and publish the response

### 5.2 Real controller

```python
class SysUsbController(BaseDiskController):
    def _get_connected_disks(self): ...  # from DiskMonitor
    def _get_disk_path(self, disk_id): ...  # from mount table
    def _perform_copy(self, src, dst): ...  # subprocess cp
    def _perform_create(self, path, data): ...  # direct write
    # ... etc.
```

The real controller's existing worker-thread + queue architecture is preserved
inside the `_perform_*` methods. The base class calls them synchronously (or
asynchronously, depending on the design).

### 5.3 Mock controller

```python
class MockSysUsbController(BaseDiskController):
    def _get_connected_disks(self):
        return list(self._disks.keys())
    def _get_disk_path(self, disk_id):
        return self._disks[disk_id]
    def _perform_copy(self, src, dst):
        shutil.copy(src, dst)
        return True
    def _perform_create(self, path, data):
        with open(path, 'wb') as f:
            f.write(data)
        return True
    # + attach_disk() / detach_disk() (hot-plug simulation)
    # + EventBus (test observation)
```

### 5.4 Key design decisions

| Decision | Options | Recommendation |
|---|---|---|
| Threading abstraction | Base handles threading vs. derived handles threading | **Derived** handles threading (the mock and real have different models); the base calls `_perform_*` synchronously |
| Disk state storage | Base maintains a disk table vs. derived | **Base** maintains a `disk_id → path` table; derived calls `_on_disk_connected/disconnected` to update it |
| Name mangling | Keep `__` vs. rename to `_` | **Rename to `_`** (single underscore) for the methods that need to be overridable; keep `__` for truly private helpers |
| `Dom0Controller` | Same refactoring vs. later | **Later** — the SysUsb refactoring is the priority (it's where the divergence bug is); Dom0 can follow the same pattern |

---

## 6. Phases

### Phase 1 — Quick fix (immediate)

Fix the divergence bug in the **current parallel mock** without refactoring:

1. `MockSysUsbController` → `COPY_FILE` handler:
   - Read `destination` from the payload
   - If `destination not in self.__source_disks_list` → log + publish
     `create_response_copy_file(filepath, disk, False, "")` + return
2. `MockSysUsbController.__handle_create_file`:
   - If `disk not in self.__source_disks_list` (and `disk != STR_REPOSITORY`)
     → log + publish `create_response_create_file(filepath, disk, "", False)` + return

Saphir-side fixes (separate issue):
3. `TransferController.__check_transfer_complete`: if `self._copy_paused` → return early
4. `TransferController.__resume_copy`: call `__check_transfer_complete()` after the loop
5. `ApplicationController.__handle_create_file`: check `success` field; if `False` → `SystemMustBeReset` + error message

**Deliverable**: Run 11 scenario passes; no regression on Runs 1–10.

### Phase 2 — Base class extraction (Safecor)

1. Create `_base_disk_controller.py` with `BaseDiskController`
2. Extract the common MQTT routing + payload validation + response formatting
   from `SysUsbController` into the base
3. Identify and extract the precondition checks (disk connected, disk exists)
4. Define the virtual `_perform_*` methods
5. Refactor `SysUsbController` to inherit from `BaseDiskController`
6. Rename mangled handler methods to single-underscore where needed
7. **Do not change any MQTT topic, payload schema, or response format**

**Deliverable**: `SysUsbController` passes its existing tests; the base class
is unit-tested in isolation.

### Phase 3 — Mock as override (Safecor emulator)

1. Rewrite `MockSysUsbController` to inherit from `BaseDiskController`
2. Override only the `_perform_*` methods + `_get_connected_disks` /
   `_get_disk_path`
3. Keep `attach_disk()` / `detach_disk()` / `EventBus` as mock-specific
   capabilities (layered on top of the base)
4. Remove the duplicated protocol handling code
5. Run the Saphir E2E test suite against the new mock

**Deliverable**: All Saphir validation scenarios pass; the mock has less code
than before (protocol handling is inherited).

### Phase 4 — Protocol conformance tests (Safecor)

1. Build a test harness that sends a fixed set of MQTT requests
2. Run against the mock (and optionally the real controller in CI with
   hardware)
3. Compare responses (schema + values)
4. Add new test cases for every edge case discovered during Saphir validation

**Deliverable**: Automated divergence detection; new preconditions in the base
class are automatically tested.

### Phase 5 — `Dom0Controller` refactoring (Safecor)

Apply the same pattern to `Dom0Controller`:
1. Extract `BaseDom0Controller` (or a more generic `BaseController`)
2. Refactor `Dom0Controller` to inherit from it
3. Rewrite `MockDom0Controller` as an override

**Deliverable**: Consistent architecture across all controllers.

### Phase 6 — Documentation

1. Update `docs/architecture.md` §6 (emulator) to reflect the new architecture
2. Update `docs/plans/emulator-plan.md` to reference the new approach
3. Document the fidelity criteria and the documented differences

---

## 7. Open Questions

| # | Question | Impact |
|---|---|---|
| 1 | Should the base class handle the worker-thread/queue abstraction, or should each derived class manage its own threading? | Affects the base class API (sync vs. async `_perform_*`) |
| 2 | Should the disk state table (`disk_id → path`) be in the base or in the derived? | Affects how `attach_disk`/`detach_disk` interact with the base |
| 3 | Is the `Dom0Controller` refactoring in scope for this plan, or a separate issue? | Affects the total effort estimate |
| 4 | Should the protocol conformance tests (Phase 4) be in the Safecor repo or the Saphir repo? | Affects where the tests live and how they're run in CI |
| 5 | What is the timeline for Phases 2–5? Is there a Safecor release cycle to align with? | Affects planning and coordination |

---

## 8. Analysis Notes (for future refinement)

- The parallel approach is **not wrong** — it is the right approach while the
  protocol is evolving and the mock needs to diverge intentionally (e.g.,
  simulate hot-plug, inject errors). The problem is that we've moved past that
  stage without transitioning the architecture.
- The override approach is **not a silver bullet** — it reduces the surface for
  divergence but doesn't eliminate it (the `_perform_*` methods can still
  behave differently). The protocol conformance tests (Phase 4) are the real
  guard.
- The **operator console** (emulator-plan.md) benefits from the override
  approach: the console drives the mock through the same base class API, so
  new features in the base are automatically available in the console.
- **Saphir's test suite** (Phase 14 of the Saphir refactoring plan) is the
  primary consumer of the E2E scenarios. The scenarios in §4.2 should be
  implemented as Saphir integration tests that drive the emulator via the
  `pytest_plugin` fixture.
