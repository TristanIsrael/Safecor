# Safecor emulator - validation tests

This document describes the issues encountered during the validation testing of the Safecor emulator.

## 1. GUI issues

### 1.1 GUI appearance

- On my MacBook, with the dark theme enabled, the GUI text is unreadable because it is written in black. Standard themes (Material for example) must be applied and the system display mode (light / dark) must be taken into account.

- The panels (`Product language`, `Logging`, etc) must be full width within their parent.

- More space must be left to the left and right of the panels for visual breathing room.

### 1.3 Broker state

The GUI must indicate whether the broker used is an external or an embedded broker.

### 1.4 Configuration change

When the user changes the selected configuration, the system state panel is not updated. For example, the screen orientation is not modified.

### 1.5 `Actions` panel

The `Actions` panel displays several `undefined undefined` lines, and no intelligible line.

### 1.6 `MQTT Events` panel

The `MQTT Events` panel displays several `undefined undefined` lines, and no intelligible line.

### 1.7 Text selection in the panels

The content of the log panels must be selectable for copy-paste.

### 1.8 Disk selection

- The selection of the directory for a disk must be done with a dialog box in addition to the text field.
- The `Attach` button must be placed to the right of the line.
- Only one disk can be attached whereas several are needed.

### 1.9 `Workflow` panel

- The `Restart domain` field must not be a text field but a drop-down list displaying only the list of started domains.
- The `Switch GUI to` field must not be a text field but a drop-down list displaying only the list of started domains.

### 1.10 `Logging` panel

- The `disk` field of `save log` must be a drop-down list displaying only the disks that are currently attached.

### 1.11 `Target` panel

- The `ping` field must be a drop-down list displaying only the disks that are currently attached.

### 1.12 Topology file loading

- To load the topology file a file selection dialog must be proposed, the text field alone is not sufficient.

### 1.13 Error display

- Errors are displayed in the shell console that launched the emulator but not in the emulator interface. For example when trying to attach a disk without having started the emulator, it fails silently in the GUI.
- If you try to attach a disk whose path does not exist, nothing happens and no error is displayed.

### 1.14 State of the Safecor domains

- After the emulator starts, the list of started domains is empty. It should contain at least the `Dom0` domain and the mocked `sys-usb`.

### 1.15 Adding a panel

- The GUI should permanently display an up-to-date list of the system components and their state. In a 2-entry table, display the name of the component and its state (see `ComponentState`).

### 1.16 Journal line selection

- It is only possible to select one line at a time in the journals, whereas it should be possible to select several lines.

### 1.17 Theme customization

- I modified the theme (Material -> iOS) and I created a qtquickcontrols2.conf file but I cannot get it to be taken into account in the python package.

### 1.18 Non-scrollable lists

- The MQTT messages list and the journal are not scrollable; when the list exceeds the height of the component, the new messages cannot be viewed.

## 2. Startup issues

### 2.1 Mandatory topology

The `--topology` argument should not be mandatory to start the application. It must be able to start without a provided topology and let the user load one.

## 3. Behaviors to check

- When the user changes the topology, the emulator should stop, load the topology and start
- What happens if the user attaches several disks with the same id and/or the same path?

---

## Correction tracking

Ledger of the reported issues, handled one by one. Statuses: **Fixed** · **To do** · **To clarify** (pending question) · **Deferred**.

| # | Issue | Type | Status | Action / plan |
|---|----------|------|--------|---------------|
| 1.1 | Unreadable dark theme · full width · margins | UI | **Fixed** (to verify on target) | Requested Material style (`QT_QUICK_CONTROLS_STYLE`) + light/dark system color-scheme (kept, degrades gracefully). To be visually checked on the target system (the offscreen test env lacks the theme APIs). |
| 1.3 | External / embedded broker | UI | **Fixed** | Reworded to `(embedded)` / `(external)`; EN/FR i18n updated. |
| 1.4 | Config change not propagated to the state | Bug | **Fixed** | `apply_configuration_settings` applies the `settings` block of a config (`screen.rotation`/`enabled`/`default_focus`, `usb.use`) to the environment (mirror of `ConfigurationHelper.__merge_configuration`); `select_configuration` calls it and the state panel re-synchronizes via `stateChanged`. |
| 1.5 | Actions panel « undefined undefined » | Bug | **Fixed** | The `Event` (dataclass) was not exposed to QML → the signal now emits a formatted line `HH:MM:SS source: text`. |
| 1.6 | MQTT Events panel « undefined undefined » | Bug | **Fixed** | Same as 1.5. |
| 1.7 | Log text not selectable | UI | **Fixed** | The delegates of the 3 journal lists go from `Text` to `TextEdit { readOnly: true; selectByMouse: true }` (selection + copy). |
| 1.8 | Disk: dialog · button to the right · multi-disks | UI | **Fixed** (dialog deferred) | `Attach` button moved to the right (after the path field); multi-disk confirmed (the `Repeater` lists the attached disks, rejects duplicated id/path). **Directory** dialog **deferred**: the `selectFolder` property of `QtQuick.Dialogs.FileDialog` is absent in this Qt offscreen build (unlike file mode, which works — see 1.12) → type the disk path in the text field. |
| 1.9 | Workflow: lists (restart / switch GUI) | UI | **Fixed** | `ComboBox` listing the started business domains. |
| 1.10 | Logging: save-log disk as a list | UI | **Fixed** | `ComboBox` listing the attached disks. |
| 1.11 | Target: ping as a list | UI | **Fixed** | `ComboBox` listing the started domains (to confirm: the ping targets a domain). |
| 1.12 | Topology loading: file dialog | UI | **Fixed** (to verify on target) | `Browse...` button + native `FileDialog` (`QtQuick.Dialogs`) in the Setup panel; it fills the path field. Declared in minimal mode (`onAccepted` only) to remain instantiable on Qt offscreen builds; the full behavior (filter/cancel) is to be checked on the target. |
| 1.13 | Errors not displayed in the GUI | Bug | **Fixed** | `attach_disk` emits a warning (GUI) if the emulator is not started, the path is invalid, or the id/path is duplicated; `__require_emulator` emits a warning before raising. Errors are no longer only in the shell. |
| 1.14 | Started domains list empty after startup | Bug | **Fixed** | New `startedDomains` property (mocked `Dom0`/`sys-usb` peers + the topology business domains); the `Restart`/`Switch GUI`/`Ping` lists are bound to it (not empty). |
| 1.15 | Component states panel | Feature | **Fixed** (to verify on target) | New `Components` panel (name + state table, `ComponentState`). `Emulator.discover_components()` queries the peers via `DISCOVER_COMPONENTS`; `ConsoleController.refresh_components()` + a periodic `Timer` (4 s) while running. |
| 1.16 | Multi-line selection of the journals | UI | **Fixed** | The 3 journal streams go from a `ListView` of `TextEdit` (one per line) to a single `TextArea { readOnly; selectByMouse }` per stream → multi-line selection + copy. |
| 1.17 | Theme customization (qtquickcontrols2.conf) | Bug | **Fixed** (to verify on target) | `QT_QUICK_CONTROLS_CONF` points to `qtquickcontrols2.conf` (the customization point: `[Controls] Style` + palette), with a fallback to the Material style if the file is absent. The file is in the wheel (hatchling); the `[tool.setuptools.package-data]` config (ineffective, hatch backend) was removed. Default style back to Material (1.1); the iOS block is documented in a comment to switch. |
| 2.1 | `--topology` mandatory | Bug | **Fixed** | `--topology` optional for `--gui`; topology loadable from the Setup panel. |
| 3.1 | Topology change → stop / load / start | Behavior | **Fixed** | `load_topology` stops, reloads and restarts if the emulator was running; a warning banner indicates that a hot change can impact the SST (possible reset). |
| 3.2 | Disks with the same id and/or the same path | Behavior | **Fixed** | The attach is rejected if the id or the path is already used (action `attach_disk_rejected` logged). |
