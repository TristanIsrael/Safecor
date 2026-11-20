# Python API

> **Scope**: the `safecor` Python library — how a DomU application talks to the platform, the module map, and the API contract rules.
>
> **Last updated**: 2026-11-20
>
> **Code**: `python/lib/src/safecor/` (imported as `safecor`).
>
> **Generated docs**: the Sphinx autodoc API reference is built from `python/lib/docs` and published on GitHub Pages (deployed on push to `main`).

> **Note (issue #223)**: the Wiki `Python-api` page is **obsolete** (it describes the old Panoptiscan architecture: `panoptiscan_lib`, `/var/run/panoptiscan/*-msg.sock`, `/etc/panoptiscan/global.conf`). This document is the offline reference for the current `safecor` `Api`.

## The `Api` (a singleton)

The `Api` is the **only** supported way for a DomU application to talk to the platform. It wraps an `MqttClient` and is fully **asynchronous** — commands return immediately and results arrive through callbacks.

- **Lifecycle**: `start()` → *ready* callback → `subscribe()` → *subscribed* callback → run.
- **Logging**: `Api.start(mqtt_client, domain_identifier, recording, logfile)` also wires the `Logger`, so every `Api().info(...)` is both logged locally and published on the `system/events/*` topics.

### Minimal usage (DomU application)

```python
import safecor
from safecor import Api, MqttFactory, Topics

# 1. Create the transport (a DomU client on the local broker UNIX socket)
mqtt_client = MqttFactory.create_mqtt_client_domu("my-domain")

# 2. Register the callbacks BEFORE starting
Api().add_ready_callback(on_api_ready)
Api().add_message_callback(on_message_recv)

# 3. Start the API
Api().start(mqtt_client=mqtt_client, recording=True, logfile="/tmp/my_app.log")

def on_api_ready():
    # 4. Subscribe once the connection is ready
    Api().subscribe(f"{Topics.SYSTEM_INFO}/response")
    Api().get_files_list("__repository__")   # async: the result arrives as a message

def on_message_recv(topic, payload):
    if topic == f"{Topics.LIST_FILES}/response":
        ...
```

The application then runs its event loop (e.g. a Qt loop); the `Api` callbacks are invoked from the MQTT client thread.

### Command groups

| Group | Methods |
|-------|---------|
| **Logging** | `debug`, `info`, `warn`, `error`, `critical` |
| **Storage** | `get_disks_list`, `get_files_list`, `read_file`, `copy_file`, `delete_file`, `get_file_fingerprint`, `create_file`, `mount_file`, `unmount`, `request_repository_path` |
| **Discovery** | `discover_components`, `publish_components` |
| **System** | `request_system_info`, `request_energy_state`, `clear_sys_usb_queues`, `request_my_config` |
| **Settings / languages** | `get_languages_list`, `get_default_language`, `get_current_language`, `set_current_language` |
| **Workflow** | `shutdown`, `restart_domain`, `switch_gui` |
| **Debugging** | `ping` |
| **Notifications** | `notify_disk_added`, `notify_disk_removed`, `notify_gui_ready` |

The full MQTT contract (topics, payloads, who answers) is in [../development/protocol.md](../development/protocol.md); the function catalogue with the emulator coverage is in [features.md](features.md).

## Non-functional requirements (API contract)

These rules apply to **all** `safecor` library API methods invoked in the MQTT event loop (callbacks, message handlers):

| # | NFR | Rationale |
|---|-----|-----------|
| NFR-1 | Functions called from MQTT callbacks must be **non-blocking**. | A blocking call (sleep, polling, I/O with timeout) in a callback stalls all other message processing. Long-running or retry logic must be delegated to the caller (e.g. a dedicated thread/task like `DirectMountManager`). |
| NFR-2 | Functions called from MQTT callbacks must have **error handling** (no unhandled exceptions). | An unhandled exception in a callback can crash the MQTT handler or leave the system in an inconsistent state. All public API methods must catch and log exceptions, returning a safe default or raising a typed error. |

## Library module map

`python/lib/src/safecor/` (imported as `safecor`):

| Module | Class(es) | Responsibility |
|--------|-----------|----------------|
| `_api.py` | `Api` | The DomU-facing asynchronous API (singleton) |
| `_api_helper.py` | `ApiHelper` | Helper utilities around the `Api` |
| `_dom0_controller.py` | `Dom0Controller` | Dom0-side command handler (see [../architecture/components/core-controller.md](../architecture/components/core-controller.md) for the dispatch pattern) |
| `_sys_usb_controller.py` | `SysUsbController` | Core DomU: real USB/disk controller (the emulator's `MockSysUsbController` stands in for it) |
| `_mqtt_client.py` | `MqttClient`, `ConnectionType` | MQTT transport (UNIX socket / TCP) |
| `_mqtt_factory.py` | `MqttFactory` | Creates a Dom0 or DomU client (incl. `create_mqtt_network_dev` for development) |
| `_mqtt_helper.py` | `MqttHelper` | MQTT payload helpers |
| `_system.py` | `System`, `topology` | System state (screen, UUID, CPU, memory), topology loading, settings, domain name. **Singleton** (`SingletonMeta` metaclass, no `__init__`, class-level cache). Also exports a **module-level global** `topology = Topology()` (populated by `System.get_topology()`). Xenstore reads via `subprocess.run(["xenstore-read", ...])`. |
| `_topology.py` | `Topology`, `Domain`, `Screen`, `Pci`, `DomainType` | Parsed topology model. **Not a singleton** — plain data class. Parsing is done by `System.__analyse_topology_struct` + `__parse_topology` (Topology never parses JSON itself). |
| `_configuration_helper.py` | `ConfigurationHelper`, `Configuration` | Applies the matching hardware configuration from the topology |
| `_request_factory.py` / `_response_factory.py` / `_notification_factory.py` | factories | Build the JSON payloads for requests / responses / notifications |
| `_topics.py` | `Topics` | The topic-name reference |
| `_constants.py` | `Constants`, `Settings`, `DiskState`, `ComponentState`, `InputType` | System-wide constants |
| `_logger.py` / `_syslogger.py` | `Logger`, `SysLogger` | Logging (local file + MQTT `system/events/*`) |
| `_file_helper.py` | `FileHelper` | File listing, fingerprinting (md5), folder traversal |
| `_disk_monitor.py` | `DiskMonitor` | inotify-based disk/file monitoring |
| `_inputs_daemon.py` / `_mouse.py` / `_keymap_fr.py` | `InputsDaemon`, `Mouse`, `KeymapFR` | Input (keyboard/mouse) handling |
| `_libvirt_helper.py` | `LibvirtHelper` | Xen/libvirt domain + CPU info (to be removed with libvirt — issue #265, see [../architecture/decisions/0005-remove-libvirt-from-dom0.md](../architecture/decisions/0005-remove-libvirt-from-dom0.md)) |
| `_xenstore.py` | `XenStore`, `XsDomain`, `XsKey` | Xen xenstore via `xen.lowlevel.xs` (transactions for writes, `xs.watch` for monitoring). Currently only `XsDomain.System` resolves; other domains are a TODO. Not yet used by library code — the live consumers are the `xenstore-read` subprocess calls in `_system.py`. |
| `_xcb_controller.py` | `XcbController` | X11/XCB GUI focus control (switch GUI, hide/show) |
| `_tasks_runner.py` | `TaskRunner` | Background task execution |
| `_components_helper.py` | `ComponentsHelper` | Component discovery helpers |
| `_debugging.py` | `Debugging` | Debugging utilities |
| `_direct_mount_manager.py` | `DirectMountManager` | Manages the direct USB mount from sys-usb via vchan+sshfs. Runs as a standalone process in a DomU. Handles the full flow: query topology → discover domid → generate vchan script → mount via sshfs. |
| `deprecated/` | — | Legacy code, do not extend |
