# Documentation refactoring plan

> **Status**: **Done** — the target structure below is implemented in `docs/` (issue #267,
> pushed 2026-11-20 on `version-2`): `architecture/` split from the monolithic
> `docs/architecture.md` (components/ + decisions/ ADR registry), `specifications/`,
> `development/`, `security/security-model.md`, `project-status.md`; `AGENTS.md` slimmed
> into a rules-and-map document; the Wiki HLD image updated.
>
> **Last updated**: 2026-11-20
>

This document explains the refactoring plan for this project documentation.

## Goals

- We want the documentation to be as specific and precise as possible for integrators of products made on Safecor.

- We want the documentation to be well structured for AI coding agents: topics dispatched in specialized documents, short documents to optimize tokens usage and analysis speed.

- We want the documentation to be useful for AI coding agents coding in Safecor **and** those coding in products based on Safecor.

## References

The documents must be dispatched between:
- The Safecor wiki for all the documentation for human beings.
- `docs/` in this project for the technical documentation for the AI coding agents.
  - This documents must contain all information needed for **offline** coding agents, even when it implies duplication with the Wiki.

## Structure

The local documents must be organized this way:
``` 
docs/
  |-- architecture/
    |-- overview.md - A global description of the architecture with a high level design picture
    |-- configuration-management.md - A description of the configuration management principle
    |-- design-rules.md - The design rules of Safecor
    |-- components/ - A folder containing all the components (One per file) with their own low level design picture    
    |-- decisions/ - A registry of the decisions made on the architecture (one document per entry)
  |-- specifications/
    |-- features.md - The document describing the features of Safecor
    |-- topology.md - The description of the Topology management
    |-- python-api.md - The description of the python API
  |-- development/
    |-- building.md - The build reference and rules
    |-- coding-rules.md - The coding standards
    |-- testing.md - The rules for the testing and the role of the emulator
    |-- protocol.md - The description of the contract between Safecor and the product
    |-- packaging.md - The packaging rules for a product based on Safecor
  |-- project-status.md - The current status of the project
  |-- security/
    |-- security-model.md - The design policy for the security of Safecor and the products made on Safecor

``` 