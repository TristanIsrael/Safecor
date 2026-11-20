# Coding Rules

> **Scope**: the coding standards of the project — formatting, linting, static analysis, naming conventions.
>
> **Last updated**: 2026-11-20

## Formatting and linting

- Use `ruff format` to format Python code consistently.
- Use `ruff check` to detect linting issues, potential bugs, and violations of coding conventions.
- Run static analysis on **all** modified Python files, including newly added files.
- Do not introduce unrelated formatting changes.
- Do not suppress linting rules unless there is a clear justification.
- Use type checking and resolve any new type errors introduced by the changes.

## Comments and commits

- Comments, documentation and commits are in **English** (even when the conversation is in another language).
- Every code commit must be linked to a GitHub issue, use the conventional format `type: subject (#issue)`, and be atomic (one commit = one issue, with the exception of tightly-coupled commits under an umbrella issue).

## Naming conventions

The codebase is the reference; when in doubt, match the surrounding code.

| Domain | Convention | Examples |
|---|---|---|
| Python — classes | `PascalCase` | `ApplicationController`, `EMAETAEstimator` |
| Python — methods / variables | `snake_case` | `start_transfer`, `remaining_time` |
| Python — private methods | double-underscore (name mangling) | `__set_system_state`, `__handle_disk_state` |
| Python — constants | `UPPER_SNAKE` | `ANTIVIRUS_NEEDED`, `TOPIC_ANALYSIS`, `DEVMODE` |
| Python — enums | `PascalCase` (no underscores) | `SystemAnalysisRunning`, `FileClean` |
| QML — components | `PascalCase` | `AnalysisPanel`, `FilesSelectionPanel` |
| QML — properties / bindings | `camelCase` | `systemState`, `queueSize`, `nbClean` |
| MQTT topics | `group/verb` structure, e.g. `saphir/analysis/{request,response,status,error,stop,resume,reset}`; `system/...` for the platform | — |

## Security rules (code level)

- `openrc` `.initd` scripts must execute commands with a regular user (`svc-*`), not root (see [building.md](building.md) and [../security/security-model.md](../security/security-model.md)).
- Do not log secrets or credentials; the logging rules are in [protocol.md](protocol.md) (`system/events/*`).
