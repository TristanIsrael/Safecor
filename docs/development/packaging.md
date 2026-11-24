# Packaging

> **Scope**: the packaging rules for a product based on Safecor — the official repository, the product packages, the local signed repository, and provisioning.
>
> **Last updated**: 2026-11-20
>
> **Companion**: [building.md](building.md) for the Safecor-side build rules (versioning, APKBUILD, checksums).

## The official repository

- URL: `https://alefbet.net/github/safecor` (an **edge** repository for development packages: `https://alefbet.net/github/safecor/edge`).
- ISO images: `https://alefbet.net/github/safecor/iso` (edge: `.../edge/iso`).

| ISO file | Description |
|----------|-------------|
| `safecor-diag-x86_64.iso` | The diagnostic app, executable from a USB key (checks VT-x/VT-d hardware compatibility). |
| `safecor-tests-x86_64.iso` | The functional and non-regression tests app, executable from a USB key. |
| `alpine-safecor-virt-x86_64.iso` | The official ISO image for the Domains running in Safecor (only the needed kernel modules and configuration; installed as `/var/lib/xen/images/alpine-virt.iso`). |

### The platform packages

| Package | Description |
|---------|-------------|
| `py3-paho-mqtt2` | Paho MQTT official library version 2.1.0 (currently not available upstream). |
| `safecor-alpine-virt` | An Alpine-*virt* kernel compiled from Alpine upstream source with additional modules for sys-usb. |
| `safecor-container-debian` | An LXC container with a minimal Debian, **only for use in DomUs**. |
| `safecor-core` | The core of the Safecor system (Dom0). Essential. |
| `safecor-diag` | A diagnostic application made for checking hardware compatibility. |
| `safecor-domu-base` | A basic package for business Domains; prepares the Domain integration in the system (local broker, vchan setup, apkovl template). |
| `safecor-gui-base` | A basic package for any GUI Domain in Safecor. |
| `safecor-hardening` | Hardening scripts and configurations for a secure system. |
| `safecor-lib` | The Safecor python library for Domains (the `safecor` package). |
| `safecor-splash` | A splash screen for Safecor apps. |
| `safecor-sys-gui` | The sys-gui Domain package. |
| `safecor-sys-usb` | The sys-usb Domain package. |
| `safecor-syslog` | A syslog facility for easier third-parties applications logging. |
| `safecor-tests` / `safecor-tests-gui` | The functional and non-regression tests application and its GUI. |

> `safecor-alpine-iso` is **deprecated** (replaced by `safecor-alpine-virt` + the virt ISO).

## Packaging a product

A product is a set of **Alpine packages** (APK), one per Domain concern (e.g. `saphir-gui`, `saphir-av-clamav`, `saphir-av-eset`):

1. **The topology declares the packages**: each business Domain entry carries its `app-package` (see [../specifications/topology.md](../specifications/topology.md)); the Domain's apkovl `etc/apk/world` is patched with that package at provisioning.
2. **Dependencies on the platform**: a product package depends on `safecor-lib` (the API), `safecor-domu-base` (the Domain integration), and — for a GUI Domain — `safecor-gui-base`.
3. **Signing**: the product's packages are signed by the product's own maintainer, who is responsible for the traceability of the package by providing the public key for the signature verification (see [../security/security-model.md](../security/security-model.md)).
4. **Repository**: the product publishes its packages in its own signed Alpine repository, referenced in the Dom0's `/etc/apk/repositories` during provisioning.

## The local signed repository (per system)

At Dom0 provisioning (`finish-core-init.sh`), the system builds a **local** Alpine repository:

1. `generate-pgp-keys.sh` — generates a local **ephemeral** PGP key-pair (unique, private key destroyed at the end of provisioning).
2. `create-local-alpine-repository.sh` — for every Domain of the topology, fetches the domain's package **and its dependencies** (`apk fetch -R`) into `/usr/lib/safecor/packages`.
3. `reindex-and-sign-repository.sh` — reindexes and signs the local repository files.
4. The public key is embedded in each Domain's apkovl (the config disk), so the Domains verify the signatures of all the packages at boot.

At every Dom0 boot, the repository content is packed into a read-only **`packages.squashfs`** image and attached to each DomU as the `xvde` block disk mounted on `/mnt/packages` (see [../architecture/decisions/0002-packages-squashfs-block-disk.md](../architecture/decisions/0002-packages-squashfs-block-disk.md)). The DomUs install their packages from this offline repository at boot (`safecor-core-init` runs `apk add` from `/mnt/packages`).

## Provisioning a device

### Manual

1. Install **Alpine Standard** from a USB stick (the Alpine version must match the repository version), with a network interface and an `admin` user.
2. Reboot, log in as `admin`, then as root add the binary repositories in `/etc/apk/repositories` (`community`, the Safecor repository, and any product-specific repositories) and the PGP keys in `/etc/apk/keys` (e.g. `wget https://alefbet.net/github/safecor/safecor.rsa.pub`), then `apk update`.
3. Install Xen: `apk add xen xen-hypervisor`, reboot, select the `Xen` GRUB entry, start the Xen service (`rc-service xenstored start`).
4. Install the product following its documentation.

### Automatic (product ISO)

The official process creates a bootable product ISO (bootable as ISO or USB key):

1. Prepare an Alpine development machine; provision the public/private keys of the product's repository.
2. Clone `aports` from gitlab; copy the product's `genapkovl-<name>.sh` and `mkimg.<name>.sh` in `aports/scripts` (make them executable).
3. Run mkimage, e.g.:
   ```console
   TMPDIR=~/tmp ./mkimage.sh --tag v3.24 --outdir ~/iso --arch x86_64 \
     --repository https://www.alefbet.net/github/safecor \
     --repository http://dl-cdn.alpinelinux.org/alpine/v3.24/main \
     --repository http://dl-cdn.alpinelinux.org/alpine/v3.24/community \
     --profile <name> --hostkeys --workdir ~/tmp
   ```
4. The ISO image is created in `~/iso`; burn it on a DVD-ROM or copy it on a USB key.
