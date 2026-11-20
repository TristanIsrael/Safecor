# Configuration Management

> **Scope**: how hardware-specific configurations are matched and applied (offline copy of the Wiki `Configuration-management` page).
>
> **Last updated**: 2026-11-20

## What is configuration management?

A configuration is a set of parameters and behaviours that can be applied to a specific hardware.

In a fleet of heterogeneous devices, for example tablets and various computers, there will be different sizes of displays, tablets will have a rotated (landscape) display with touchscreen while computers will have a regular (landscape) display. But you might want to rotate the screen differently to have a portrait orientation. Some hardware will need to be disabled for security or operational reasons, particularly PCI devices or buses.

For all these reasons Safecor provides a configuration management system that helps you define settings specific to a device family or type.

## Settings hierarchy

Some of the settings can be defined on the kernel's command line (for an ISO image or network boot) or only in the [Topology](../specifications/topology.md). The hierarchy rule defines which setting is kept over the others.

*When a setting is defined in the Topology **and** on the command line, the **command line** value is kept.*

## Device management

The device is identified with the help of the [DMI (Desktop Management Interface)](https://en.wikipedia.org/wiki/Desktop_Management_Interface) API.

Safecor reads and analyzes the DMI information provided by the firmware of the device, and this information can be used to match a configuration.

## Defining a configuration

A configuration is defined in the [topology](../specifications/topology.md). A specific section can be added in a regular topology file:

```
"configurations": [
    {
        "name": "Durabook R8",
        "identifier": {
            "sys_vendor": "Durabook",
            "product_name": "R8AA"
        },
        "settings": {
            "gui": {
                "screen": {
                    "rotation": 90
                }
            },
            "pci": {
                "blacklist": "00:0d.0"
            }
        }
    }
]
```

The field `configurations` is an array and can be used to define as many configurations as needed.

## Identify a product or a unit

All the files located in `/sys/class/dmi/id/` on a regular device can be used to identify a device.

The device can be identified with the help of the following DMI fields:

| Field | Description |
|--|--|
| `product_name` | This is often the model of the device |
| `product_serial` | This is the serial number of the device which identifies the type of device |
| `product_sku` | This is a SKU that identifies a product, it can be empty |
| `product_uuid` | This field should identify a specific unit and can be used to target one unit specifically |
| `sys_vendor` | This field identifies the manufacturer of the device |

There may be more or less fields in the directory `/sys/class/dmi/id/` but you should be able to find a combination that will match a product or a specific unit in your fleet.

The field `identifier` in the configuration is the place where the device or unit must be identified using the name of a file located in `/sys/class/dmi/id/` as the key and the text it contains as the value.

For example, on a Durabook R8 device:

```
$ cat /sys/class/dmi/id/sys_vendor
Durabook

$ cat /sys/class/dmi/id/product_name
R8AA
```

If you want to target this model, create a configuration like this:

```
{
    "name": "Durabook R8",
    "identifier": {
        "sys_vendor": "Durabook",
        "product_name": "R8AA"
    },
    "settings": { }
}
```

Now if you want to create a configuration for one specific unit, you can do:

```
{
    "name": "Abraham's Durabook R8",
    "identifier": {
        "sys_vendor": "Durabook",
        "product_name": "R8AA",
        "product_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
    },
    "settings": { }
}
```

## Default configuration

If the device running Safecor matches none of the configurations, the default configuration will be applied. The default configuration corresponds to all the settings outside of the section `configurations` in the topology.
