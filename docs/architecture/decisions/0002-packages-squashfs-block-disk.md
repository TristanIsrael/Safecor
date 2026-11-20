# 0002 — The local Alpine repository as a squashfs block disk

**Status**: Accepted (v2)

## Context

The DomUs must install their packages from a **local, signed** Alpine repository (the DomUs have no network interface by default). In v1 the repository was shared between Dom0 and the DomUs with a 9p share; the 9p exports in the generated xl configurations widened the attack surface (a DomU could see more than its own repository) and added a kernel-level dependency in every domain.

## Decision

- The local Alpine repository is packed on Dom0 into a **read-only `packages.squashfs` image** (`create-packages-squashfs.sh`, rebuilt at every Dom0 boot).
- It is attached to each DomU as a **plain block disk** (`xvde`, HVM: `sde`) and mounted read-only on `/mnt/packages` — the fstab entry is part of the apkovl template:
  ```
  /dev/xvde  /mnt/packages  squashfs  ro  0 0
  ```
- The generated xl configurations carry **no 9p shares anymore** (neither the repository nor the `storage` share). File access for the DomUs goes through the **MQTT file API** (served by the core controller) and the **direct USB mount** (v2).

## Consequences

- DomUs are fully offline for package installation; the squashfs is rebuilt at every Dom0 boot so the image always matches the local repository content.
- The repository image is read-only and block-level: a DomU cannot write to it, see other domains' content, or tamper with the signatures.
- Package signing is unchanged: the local repository is signed with an ephemeral PGP key-pair generated at provisioning (see [../../security/security-model.md](../../security/security-model.md)).
