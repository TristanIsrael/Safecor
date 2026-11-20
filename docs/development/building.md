# Building

> **Scope**: the build reference and rules — versioning, Alpine packages (APKBUILD), checksums, OpenRC scripts, CI.
>
> **Last updated**: 2026-11-20

## Versioning

Scheme `MAJOR.MINOR.PATCH` (e.g. `2.2.0`):

| Change | Bump |
|--------|------|
| A bug fix | the last digit (patch) only |
| A new feature | the second digit (minor), reset the last digit to 0 |
| Major | only by the product maintainer |

When the components versions are modified, the Alpine Linux packages must be updated to reflect the components versions.

## Alpine packages (APKBUILD)

- The package definitions live in `setup/packages/safecor/<package>/` (one folder per package, an `APKBUILD` and the package resources).
- **Checksums**: every file listed in `source=` must carry a `sha512` checksum in `source=`. After **any** modification of a packaged resource, recalculate the checksums before committing/pushing (e.g. `apk-tools`/`apkoor` or a manual `sha512sum` update in the APKBUILD).
- The `setup/iso/` scripts generate the ISO images (diagnostic, tests, virt).

The package list and the product packaging rules are in [packaging.md](packaging.md).

## OpenRC scripts

- When creating an `openrc` `.initd` file, **do not write python code inside the script**: write a python file instead and call it from the `.initd` script.
- The `.initd` scripts must execute commands with a **regular user** (`svc-*`), never root. If no user matches the script's subject, create one in the package's `post-install` script. See [../security/security-model.md](../security/security-model.md).

## CI

GitHub Actions:

- `build-all.yml` — builds the packages/images.
- `documentation.yml` — builds the Sphinx docs and deploys them to GitHub Pages (on push to `main`).
