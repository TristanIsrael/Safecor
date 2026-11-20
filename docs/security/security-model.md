# Security Model

> **Scope**: the design policy for the security of Safecor and of the products made on Safecor (offline copy of the Wiki `Security` page, with the v2 state).
>
> **Last updated**: 2026-11-20

## Security strategy

The security strategy relies on some key design concepts:

- **Isolation**: the components of the system are separated from each other. It means that they belong to their own virtual machine and have no direct contact with the other components. Thus the threats cannot contaminate the whole system.
- **Protocol break**: the communication between the components uses a very simple data protocol with a very low attack surface. An attack from outside the system cannot propagate inside the system using TCP-IP or USB for example, as these protocols are confined in their respective components (`sys-usb`, `sys-net`, …) and the data flow uses another data protocol and channel (MQTT over vchan — see [../architecture/components/messaging.md](../architecture/components/messaging.md)).
- **Collaboration**: the components of the system that don't need to manipulate files or external data don't have access to them. Instead, they collaborate with other components to get the information or data they need. This reduces the risk of contaminating the core of the system.
- **Simplicity**: the architecture of the core is very simple, and this simplicity limits configuration or design weaknesses that could be exploited by threats. This is a major [design rule](../architecture/design-rules.md).

## Hardening rules

### Services

The services are executed as a **normal user** (without privilege). The user `root` is never used for any service nor application in the system.

Each service is associated with its own user (`svc-*`) and belongs to the group `safecor`. Its configuration files and the files it creates are owned by its user; the files it needs to access but does not own are accessible as long as they belong to the group `safecor`.

The following rules apply:

- A service is not allowed to list, read or modify the configuration files of another service.
- A service is not allowed to list, read or modify any of the operating system's configuration files.

These rules apply in the Dom0, the Driver Domains and the User Domains. In the product's Domains, designers are encouraged to apply these rules to avoid creating leaks in the system.

### Users and groups

The shared contents, like the storage, can be accessed R/W with a user that belongs to the group `safecor`. The group `safecor` is added to the Domain by the package `safecor-domu-base` (see [../development/packaging.md](../development/packaging.md)).

## Analysis of the data lifecycle

In this chapter we analyze the potential data remanence on the system after its usage.

It may concern:

- the files created during the system's usage
- the files read from an external device (USB storage for example)
- the data copied in memory
- the secrets embedded in the system (private keys)

*To be completed.*

## Packages traceability

Alpine Linux official repository provides cryptographically signed packages. Their signature is embedded inside the package file and the signing keys are managed by the Alpine maintainers. When a package is installed, each package's signature is verified before installation; the public key is embedded in the system itself. Unless both maintainers' keys and systems' keys are corrupted, it is almost impossible to install a corrupted package.

The product's packages are signed by its own maintainer, who is responsible for the traceability of its packages by providing the public key for the signature verification.

When a system based on Safecor is provisioned, a local repository is created with all the packages needed for the Domains creation. This local repository is signed with an **ephemeral** key-pair randomly generated during the provisioning. The key-pair is unique and the private key is removed at the end of the provisioning process. The public key is embedded into each Domain configuration (the apkovl on the config disk). When the Domains boot, they verify the signatures of all the packages using the public key of the local repository (see [../development/packaging.md](../development/packaging.md)).

## Local storage security

The local storage (the repository backing store) is an image file created during the system boot and destroyed during its shutdown.

The image is ciphered before being mounted in the Dom0. It is considered dangerous and a potential source of leaks: that is the reason why it can never be reused.

The ciphering process relies on [cryptsetup (LUKS)](https://gitlab.com/cryptsetup/cryptsetup) and a strong **ephemeral** encryption key (AES-512 XTS) randomly generated during the boot of the system. The image file is destroyed when the system is shut down; in the case the image file persists on the disk, it is destroyed on the next boot. Even if the image file was extracted from the system, it could not be deciphered because the (ephemeral) random key used for ciphering is lost as soon as the file has been ciphered and is never written on the disk.

## v2 attack-surface notes

- **PCI passthrough**: PCI devices are considered dangerous and are captured by dedicated DomUs (`sys-usb` for USB, `sys-net` for network) — which requires IOMMU (VT-d / AMD-Vi). The DomUs that capture them run unprivileged and are hardened; see [../architecture/overview.md](../architecture/overview.md).
- **No 9p, no shared mounts**: the DomUs have no 9p shares and no shared block disk (except the read-only `packages.squashfs`); data exchange goes through the MQTT file API and the direct USB mount (see [../architecture/decisions/0002-packages-squashfs-block-disk.md](../architecture/decisions/0002-packages-squashfs-block-disk.md) and [../architecture/components/direct-usb-mount.md](../architecture/components/direct-usb-mount.md)).
- **vchan instead of serial channels**: the inter-domain channels are created at runtime by unprivileged `vchan-socket-proxy` servers, and the Xen device nodes are exposed only to the `safecor` group (see [../architecture/components/vchan-tunnel-manager.md](../architecture/components/vchan-tunnel-manager.md)). Restricting the xenstore write grants to the vchan subtree is a follow-up (issue #261).
- **libvirt removal (issue #265)**: `libvirtd` currently runs on Dom0 as a query-only daemon; removing it is planned to reduce the attack surface (design rule #10) — see [../architecture/decisions/0005-remove-libvirt-from-dom0.md](../architecture/decisions/0005-remove-libvirt-from-dom0.md).
