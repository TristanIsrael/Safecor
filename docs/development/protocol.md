# Protocol

> **Scope**: the MQTT contract between the Safecor platform and a product — topics, payloads, message shapes, and who answers. This is the **offline** reference (copy of the Wiki `Protocol` page, **code-authoritative names**, with the mismatches noted inline).
>
> **Last updated**: 2026-11-20
>
> **Code**: `_topics.py` (topic names), `_request_factory.py` / `_response_factory.py` / `_notification_factory.py` (payloads), `_dom0_controller.py` / `_sys_usb_controller.py` (handlers).

## Topic model

Topics use a `group/verb` structure. Every **query/answer** pair uses the suffixes `/request` and `/response` (same topic, different suffix); **notifications** are published on a bare topic. The three message shapes:

- **Request** — a command from a DomU to the platform (`RequestFactory` builds the payload), published on `<topic>/request`.
- **Response** — the answer, published on `<topic>/response`.
- **Notification** — an asynchronous event with no expected reply, published on a bare topic.

Transports and the message bus architecture: [../architecture/components/messaging.md](../architecture/components/messaging.md).

> **Authoritative names**: the **code** is authoritative for topic and field names. The Wiki `Protocol.md` deviates in a few places (marked **⚠** below); the code names are the ones a product must use. The related issues track the Wiki corrections.

## Disks and file management

### List connected disks

*Requests the list of external storage disks connected to this system.*

- Request: `system/disks/list_disks/request` — payload `{}`
- Response: `system/disks/list_disks/response`

```json
{ "disks": [ "disk1", "disk2" ] }
```

- `disks` (list): the list of disk names as strings. A disk may contain multiple partitions; each partition is considered a disk.

### List files of a disk

- Request: `system/disks/list_files/request`

```json
{ "disk": "disk1", "recursive": false, "from_dir": "", "name_filters": [] }
```

- `disk` (str): the disk the request relates to.
- `recursive` (bool): if true, the listing covers every subdirectory starting from `from_dir`. Default false.
- `from_dir` (str): if set, only the files of this directory (and subdirectories if recursive). Default `""`.
- `name_filters` (list): filter files by their extension, e.g. `[".zip"]`. **⚠ (P4, #219/#218)**: the Wiki says `name_filter`; the code uses `name_filters` (see also #218: the filter is silently ignored at runtime).
- Response: `system/disks/list_files/response`

```json
{ "disk": "disk1", "files": [ { "type": "file", "path": "/", "name": "my_file.txt", "size": 1234 } ] }
```

- `files` (list): `type` ("file" or "folder"), `path` (complete path), `name`, `size` (int, bytes; absent for folders).

### Mount a virtual disk or an archive

*Mounts a `.iso`, `.zip`, `.tar`, … as a new disk; a disk state notification is sent on success.*

- Request: `system/disks/mount_file/request` — `{ "disk": "disk1", "filepath": "/my/folder/the_image.iso" }`
- The file is mounted **read-only**. Accepted extensions: `.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tar.zst`, `.tar.lz4`, `.cpio.gz`, `.tgz`, `.xz`, `.gz`, `.bz2`, `.lzma`, `.lz`, `.lz4`, `.zst`, `.Z`, `.cpio`, `.a`, `.ar`, `.deb`, `.zip`, `.jar`, `.war`, `.ear`, `.apk`, `.7z`, `.xar`, `.pkg`, `.lha`, `.lzh`, `.cab`, `.rar`, `.mtree`.

### Unmount a virtual disk

- Request: `system/disks/unmount/request` — `{ "disk": "my_disk.iso" }`. A disk state notification is sent on success.

### Read a file into the repository

*Reads a file from an external disk into the local repository.*

- Request: `system/disks/read_file/request` — `{ "disk": "disk1", "filepath": "/my/folder/my_file.txt" }`
- Answer: the `system/disks/new_file` **notification** (see Notifications).

### Copy a file to a storage

- Request: `system/disks/copy_file/request` — `{ "disk": "source_disk", "filepath": "/my/file.txt", "destination": "destination_disk" }`
- Response: `system/disks/copy_file/response`

```json
{ "filepath": "/my/file.txt", "status": "ok", "fingerprint": "12345678901234567890" }
```

- `status` (str): "ok" or "error". `fingerprint` (str): the fingerprint of the file on the destination disk.

### Delete a file

*Deletes a file from a disk, including the repository. The `deleted_file` notification is sent.*

- Request: `system/disks/delete_file/request` — `{ "disk": "disk1", "filepath": "/my/folder/my_file.txt" }`

### File fingerprint

*Computes the unique fingerprint of a file (MD5).*

- Request: `system/disks/file_fingerprint/request` — `{ "disk": "disk1", "filepath": "/my/folder/my_file.txt" }`
- Response: `system/disks/file_fingerprint/response`

```json
{ "disk": "disk1", "filepath": "/my/folder/my_file.txt", "fingerprint": "12cfd565ff54caa12" }
```

**⚠ (P1, P2, #219)**: the Wiki says the topic is `file_footprint` and the response field is `footprint`; the code uses `file_fingerprint` and `fingerprint`. Use the code names.

### Create a new file

*Creates a new file on a disk, including the repository.*

- Request: `system/disks/create_file/request`

```json
{ "disk": "disk1", "filepath": "/my/folder/my_file.txt", "data": "KJsh76S8912Hgsgfd54222Rtfg==", "compressed": false }
```

- `data` (str): base64 data. `compressed` (bool): for binary data, the data can be compressed with **zlib (deflate)** and this field must be true. Default false. **⚠ (M1)**: the Wiki says "GNU zip"; the code uses `zlib.compress` (deflate).
- Response: `system/disks/create_file/response`

```json
{ "filepath": "/my/folder/my_file.txt", "disk": "disk1", "fingerprint": "12cfd565ff54caa12", "success": true }
```

**⚠ (P7)**: the Wiki only references the `new_file` notification for the response; the code also publishes this `create_file/response` payload.

### Request information about a disk 📄

*Documented in the Wiki, **not implemented** in the code* (no topic, no handler — U1, #220).

- Request: `system/disks/storage_info/request` — `{ "disk": "__repository__" }`
- Response: `system/disks/storage_info/response` — `{ "disk", "free", "total", "used" }` (bytes).

## Workflow

### Shutdown the system

- Request: `system/workflow/shutdown/request` — `{}`
- Response: `system/workflow/shutdown/response`

```json
{ "state": "accepted", "reason": "" }
```

- `state` (str): `accepted` or `refused`. `reason` (str): present when refused.

### Restart a Domain

- Request: `system/workflow/restart_domain/request`

```json
{ "domain_name": "my_domain", "forced": false }
```

- `domain_name` (str): must match an existing Domain (`sys-usb`, `sys-gui`, or a domain defined in the `topology.json`).
- `forced` (bool): if true, the restart is forced in Dom0, otherwise the Domain restarts itself.
- Response: `system/workflow/restart_domain/response` — `{ "domain_name", "state", "reason" }` (same semantics as shutdown).

## Logging

Log events are **notifications** published by the `Logger` of any domain (and by the product's `Api().debug/info/warn/error/critical` calls):

| Topic | Payload |
|-------|---------|
| `system/events/debug` | `{ "component", "module", "datetime", "description" }` |
| `system/events/info` | *same shape* |
| `system/events/warning` | *same shape* |
| `system/events/error` | *same shape* |
| `system/events/critical` | *same shape* |

### Set the log level

*Defines the log level under which the events are ignored.*

- Topic: `system/events/set_loglevel` — `{ "level": "info" }` (python logging levels).

### Save the log into a file

- Topic: `system/events/save_log` — `{ "disk": "disk1", "filename": "logfile.txt" }`.

## Monitoring 📄

*Documented in the Wiki, **not implemented** in the code* (no topic, no handler — U2, #220/#227; the "Monitoring" capability listed in the Wiki `Capabilities` page is also absent — U3/U4, #227).

- Request: `system/monitoring/request` — `{ "operation": "start|stop", "target": "all", "delay": 60 }`
- Response: `system/monitoring/response` — `{ "domain", "operation", "accepted" }`.

## Miscellaneous

### Discover the components of the system

- Request: `system/discover/components/request` — `{}`
- Response: `system/discover/components/response`

```json
{ "components": [ { "id": "<unique id>", "domain_name": "<domain>", "label": "<free label>", "type": "<type>", "state": "<state>", "version": "<version>", "description": "<long description>" } ] }
```

**⚠ (M2)**: the Wiki types `state` as `(int)`; the code `ComponentState` values are **strings** (`ready`, `error`, …).

### Get the energy state

- Request: `system/energy/state/request` — `{}`
- Response: `system/energy/state/response` — `{ "battery_level": 100.0, "plugged": 1 }`
  - `battery_level` (float): 0.0 (empty) to 100.0 (full). `plugged` (int): 1 if powered by an external source.

### Get information on the system

- Request: `system/info/request` — `{}`
- Response: `system/info/response`

```json
{
    "core": { "version": "1.1", "debug_on": false },
    "system": {
        "os": { "name", "release", "version" },
        "machine": { "arch", "processor", "platform", "cpu": { "count", "freq_current", "freq_min", "freq_max", "percent" }, "memory": { "total", "available", "percent", "used", "free" }, "load": { "1", "5", "15" } },
        "boot_time": 1748036696.0,
        "uuid": "11ec0800-4fb9-11ef-bd38-ad993f2e7700",
        "storage": { "total": 12345678, "used": 0, "free": 12345678, "files": 0 }
    }
}
```

**⚠ (P6, #222)**: the Wiki says `storage.files_count`; the code uses `storage.files`.

### Clear sys-usb commands queue

- Request: `system/sys-usb/clear-queues/request` — `{}`
- Response: `system/sys-usb/clear-queues/response` — `{ "success": true, "reason": "" }`

## Settings

### Languages

| Function | Request topic | Response |
|----------|---------------|----------|
| Get the languages list | `system/settings/languages/list/request` | `system/settings/languages/list/response` — `{ "languages": [ "en", "fr" ] }` |
| Get the default language | `system/settings/languages/default/request` | `system/settings/languages/default/response` — `{ "language": "en" }` |
| Get the current language | `system/settings/languages/current/request` | `system/settings/languages/current/response` — `{ "language": "en" }` |
| Set the current language | `system/settings/languages/set/request` — `{ "language": "en" }` | `system/settings/languages/set/response` — `{ "language": "en" }` |

**⚠ (B1, #217)**: the intended contract for the **list** request is `system/settings/languages/list/request` (the Dom0 handler subscribes to `Topics.LIST_LANGUAGES`). But `Api.get_languages_list()` publishes to `system/settings/languages/request` (as the Wiki documents) → the list requests are **dropped**. This is a known code bug tracked by #217; until it is fixed, a product should not rely on `get_languages_list()`.

### Setting changed (notification)

- Topic: `system/settings/changed` — `{ "key": "<the setting name>", "value": "<the setting value>" }`

## Graphical User Interface

### Switch to another graphical interface

- Request: `system/gui/switch/request` — `{ "domain": "<domain name>" }`
- **⚠ (P5, #222)**: the Wiki says the field is `domain_name`; the code uses `domain` (`_request_factory.py` `create_request_switch_gui`, read with `payload.get("domain")` in `_dom0_controller.py`).
- Response: `system/gui/switch/response` — `{ "state": "accepted|refused", "reason": "" }`

## Notifications

### A new file is available

*Sent when a file has been copied or created on a disk, including the repository.*

- Topic: `system/disks/new_file`

```json
{ "disk": "disk1", "filepath": "/a/folder/my_file.txt", "source_fingerprint": "acd653c5a8b988cbdbabd65", "dest_fingerprint": "acd653c5a8b988cbdbabd65" }
```

**⚠ (P3, #219)**: the Wiki says `source_footprint` / `dest_footprint`; the code uses `source_fingerprint` / `dest_fingerprint`. The two values must match.

### The state of a disk changed

- Topic: `system/disks/state` — `{ "disk": "disk1", "state": "connected" }`
- States: `connected`, `disconnected`, `mounted`, `unmounted`.

### The GUI is ready

*The splash screen must be removed.*

- Topic: `system/workflow/gui_ready` — `{}`

### A file has been deleted

*Sent after a successful `delete_file`.*

- Topic: `system/disks/deleted_file` — `{ "disk": "disk1", "filepath": "/my/file.ext" }`

## Debugging

### Ping a Domain

*Pings a Domain like ICMP does.*

- Request: `system/debugging/ping/<domain name>/request`

```json
{ "id": 1, "source": "my-domain", "data": "ad6452fbc4a56", "sent_at": 1234567891239.123 }
```

- Response: `system/debugging/ping/<domain name>/response` — echoes the request payload.
  - `id` (int): unique and increasing. `source` (str): the querying domain (the response goes back to it). `data` (str): random debug data. `sent_at` (float): timestamp in milliseconds.

## Topology

### Get my config

*Requests the topology configuration relevant to the calling Domain (its `direct_mount` settings, screen parameters, languages, PCI blacklist).*

- Request: `system/topology/my_config/request` — `{}`
- Response: `system/topology/my_config/response`

```json
{
    "product_name": "Saphir",
    "use_usb": true,
    "repository_disabled": false,
    "domains": [
        { "name": "sys-usb", "domain_type": 1, "direct_mount": null },
        { "name": "myapp-gui", "domain_type": 2, "direct_mount": { "mode": "rw" } }
    ],
    "screen": { "width": 1920, "height": 1080, "rotation": 0, "enabled": true, "default_focus": "myapp-gui" },
    "languages": [ "en", "fr" ],
    "default_language": "en",
    "pci_blacklist": [ "00:1f.2" ]
}
```

- `domains[].domain_type` (int): 1 = core, 2 = business. `domains[].direct_mount`: the [direct mount](../architecture/components/direct-usb-mount.md) configuration, or null.

## Notes

- The repository can be referenced as the disk `__repository__`.
- 📄 functions (storage_info, monitoring) are **documented in the Wiki but not implemented** in the code — a product exercising them would hang. They are tracked by #220/#227.
