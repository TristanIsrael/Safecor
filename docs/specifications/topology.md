# Topology

> **Scope**: the `topology.json` file — what it defines, how it is loaded, and the resource allocation rules (offline copy of the Wiki `Topology` page, **code-authoritative key names**).
>
> **Last updated**: 2026-11-20
>
> **Code**: `_system.py` (`System.get_topology`, `get_topology_struct`, `__analyse_topology_struct`, `__parse_topology`), `_topology.py` (`Topology`, `Domain`, `Screen`, `Pci`, `DomainType`), `_configuration_helper.py` (`ConfigurationHelper`).

The topology works like an *infra-as-code* mechanism: it delegates (part of) the definition of the system technical characteristics to the developer of the product.

In Safecor, the topology definition allows to:

- declare the product name and other information,
- enable/disable the USB bus,
- enable/disable the graphics,
- blacklist PCI devices,
- define a package to install for the Graphical User Interface (GUI),
- define the memory allocated to the GUI,
- rotate the screen,
- define the CPU allocation to the Domains,
- declare business Domains, their memory and package to install,
- define [configurations](../architecture/configuration-management.md) to match specific hardware.

This is a typical `topology.json`:

```json
{
    "usb": {
        "use": 1
    },
    "pci": {
        "blacklist": [ "00:0d.0" ]
    },
    "screen": {
        "enabled": 1,
        "rotation": 90,
        "default_focus": "myapp-gui"
    },
    "vcpu": {
        "groups": {
            "group1": 0.8
        }
    },
    "business": {
        "domains": [
            {
                "name": "myapp-gui",
                "app-package": "myapp-gui",
                "memory": 4096,
                "vcpu_group": "group1",
                "temp_disk_size": 4096,
                "swap_size": 4096,
                "has_gui": 1,
                "direct_mount": { "mode": "rw" }
            },
            {
                "name": "myapp-function2",
                "app-package": "myapp-function2",
                "memory": 4096,
                "vcpu_group": "group1"
            }
        ]
    },
    "repository": {
        "disabled": false
    },
    "storage": {
        "type": "disk",
        "index": 1,
        "size": -1
    },
    "product": {
        "name": "Saphir",
        "splash_bgcolor": "#1ca9f7",
        "languages": [ "en", "fr" ],
        "default_language": "en"
    }
}
```

## Sections

### `usb`

The `usb` section defines the settings for the USB functions of the system.

| Key | Type | Description |
|--|--|--|
| `use` | int | Set to 1 if the Domain `sys-usb` should be setup and used, else 0. |

### `screen`

The `screen` section defines the settings for the monitors.

| Key | Type | Description |
|--|--|--|
| `enabled` | int | Set to 1 if the system includes any GUI. |
| `rotation` | int | Defines the rotation of the screen if needed, for example on a tablet. Accepted values are: 0, 90, 180 or 270. |
| `default_focus` | string | Defines the graphical Domain that has the focus on boot. It will receive the inputs exclusively. |

### `storage`

The `storage` section defines the settings for the local storage (the encrypted repository backing store on Dom0).

| Key | Type | Description |
|--|--|--|
| `type` | str | Set it to `disk` to enable the creation of an encrypted storage file on the disk |
| `index` | int | If the system embeds multiple disks, this is the index of the disk to use for the storage (starting at 1) |
| `size` | int | The size of the storage in MB. Set it to `-1` to use all available space. |

> **Note**: this section is consumed by the **core orchestrator** (the non-Python boot/provisioning scripts that create the encrypted storage image). It is **not** parsed by the Python `System.__analyse_topology_struct` (only `usb`/`screen`/`vcpu`/`business`/`pci` are read). Do not expect it in the `Topology` object.

### `business`

The `business` section defines the settings for the business components of the system, including the Domains.

| Key | Type | Description |
|--|--|--|
| *domains* | *array* | *This section defines the domains which will be created on startup.* |
| `domains.<entry>.name` | string | Gives a name to the Domain. |
| `domains.<entry>.app-package` | string | Defines the package (APK) which will be installed in the Domain. |
| `domains.<entry>.memory` | int | Defines the memory, in MB, which should be allocated to the Domain. |
| `domains.<entry>.temp_disk_size` | int | If defined, a disk will be created with this size in `MB` and mounted in the Domain on `/tmp` |
| `domains.<entry>.swap_size` | int | If defined, a swap disk will be created with this size in `MB` |
| `domains.<entry>.has_gui` | int | If defined, the Domain will produce graphical content. `screen.enabled` should also be set in this case. |
| `domains.<entry>.vcpu_group` | string | The name of the `vcpu.groups` entry the domain's vCPUs are drawn from. |
| `domains.<entry>.direct_mount` | object | If defined, the Domain will mount `/media/usb` directly from `sys-usb` via vchan+sshfs. See below. |

The `direct_mount` object:

| Key | Type | Description |
|--|--|--|
| `mode` | string | `"ro"` for read-only access, `"rw"` for read-write. Default is `"rw"`. |

### `repository`

The `repository` section controls the shared repository.

| Key | Type | Description |
|--|--|--|
| `disabled` | bool | If `true`, the repository is not created and DomUs cannot access `__repository__`. Default is `false`. |

> **Note (v2)**: the repository is **not** mounted in the DomUs (the v1 9p share is gone). File access goes through the **MQTT file API** and the **direct USB mount** — see [../architecture/overview.md](../architecture/overview.md) and [../architecture/decisions/0002-packages-squashfs-block-disk.md](../architecture/decisions/0002-packages-squashfs-block-disk.md).

### `product`

The `product` section defines the settings for the definition of the product and global settings.

| Key | Type | Description |
|--|--|--|
| `name` | string | The name of the product |
| `splash_bgcolor` | string | The color that will be added in the background of the boot logo |
| `languages` | list | The list of languages handled by the product, including the business components |
| `default_language` | string | The default language that will be used by the system |

## Resource management

Resources (CPU, memory) can be affected to Domains (sys-gui and business Domains) as portions of the platform resources.

### vCPU management

The following rules apply:

- the Dom0 and sys-usb Domains can't be configured:
  - Dom0 will have the 2 first vCPUs unless the system has less than 4, so it gets only the first.
  - sys-usb will have the same vCPUs as Dom0.
- the configurable groups are:
  - sys-gui will have the 2 next vCPUs by default unless the system has less than 4, so it gets only the second one. This value can be modified in `topology.json`.
  - the rest can be divided in groups and affected to the Domains.

The proportions are:

- 15% to Dom0/sys-usb (shared) → minimum value is 1
- 75% for the rest of the system:
  - 20% to sys-gui by default (overridable)
  - 80% to the business Domains, divisible into groups.

Groups of vCPUs are declared in the section `vcpu.groups` which represents 100% of the allocatable vCPUs (75% of the system). Then each business domain can have a group allocated using the keyword `vcpu_group`.

Example:

```json
"vcpu": {
    "groups": {
        "my_group": 0.8
    }
}

"business": {
    "domains": [
        {
            "name": "myapp-function1",
            "vcpu_group": "my_group"
        }
    ]
}
```

## How the topology is loaded (code flow)

`System.get_topology()` (Dom0) loads `/etc/safecor/topology.json`, converts it to an internal struct (`get_topology_struct`), parses it into a `Topology` object (`__parse_topology`), and applies the matching hardware configuration (`ConfigurationHelper.apply_configuration`). The result is the authoritative description of the running system: product name, screen, USB, languages, default language, and the **domain list** (the core `sys-usb` domain plus the business domains).

- `System` is a **singleton** (`SingletonMeta` metaclass, no `__init__`, class-level cache) and also exports a **module-level global** `topology = Topology()` populated by `System.get_topology()`.
- `Topology` / `Domain` are **plain data classes** (not singletons); parsing is always done by `System`. `Domain` fields: `name`, `domain_type`, `memory`, `vcpus`, `cpu_affinity`, `package`, `has_gui`, `vcpu_group`, `temp_disk_size`, `swap_size`.
- At runtime, a DomU can query its own configuration over MQTT with `system/topology/my_config` — see [../development/protocol.md](../development/protocol.md).

## Key names: code is authoritative

> **Wiki deviation (issue #226)**: the Wiki `Topology.md` **tables** use different key names than both the code and the Wiki's own example. The **code** names are authoritative (used by `_system.py`):
>
> | Section | Wiki table says | Code / example says |
> |---------|-----------------|---------------------|
> | `screen` | `enable` | `enabled` |
> | `business.domains[]` | `package` | `app-package` |
> | `business.domains[]` | `temp_disk` | `temp_disk_size` |
>
> Always use the key names of this document (the code's) when writing a `topology.json`.

## See also

- [../architecture/configuration-management.md](../architecture/configuration-management.md) — the `configurations` section (hardware matching)
- [../development/protocol.md](../development/protocol.md) — `system/topology/my_config`
