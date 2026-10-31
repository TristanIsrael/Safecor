#!/usr/bin/env python3
"""
Generate the complete API reference RST for the safecor package.

The class list is built by introspecting the ``safecor`` module (no
hardcoded list) and grouped by the module each class is defined in.
Every directive carries an explicit module prefix (``safecor.X``) so
autodoc can import the class.

Usage:
    python scripts/gen_api_rst.py

Output:
    docs/source/api/safecor.generated.rst
"""

import inspect
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import safecor  # noqa: E402

# Names that are re-exported third-party objects or module-level
# instances, not part of the public class API.
EXCLUDED = {"topology", "logging"}


def collect_classes():
    """Return the public classes of the safecor package, grouped by module."""
    groups = {}
    for name in dir(safecor):
        if name.startswith("_") or name in EXCLUDED:
            continue
        obj = getattr(safecor, name)
        if not inspect.isclass(obj):
            continue
        module = obj.__module__
        if not module.startswith("safecor"):
            continue
        groups.setdefault(module, []).append(name)
    return {module: sorted(names) for module, names in sorted(groups.items())}


def rst_title(text, char):
    return "\n".join([text, char * len(text)])


def generate(groups):
    lines = [
        ".. _safecor-api-classes:",
        "",
        rst_title("Safecor API - Complete Class List", "="),
        "",
        "Complete reference of the ``safecor`` package, grouped by the",
        "module each class is defined in. This page is auto-generated",
        "from the module introspection; do not edit it by hand. Run",
        "``python scripts/gen_api_rst.py`` to regenerate it.",
        "",
    ]

    for module, names in groups.items():
        words = [w.capitalize() for w in module.rsplit(".", 1)[-1].split("_") if w]
        section = "{} API".format(" ".join(words))
        lines.append(rst_title(section, "-"))
        lines.append("")
        lines.append("Classes defined in the ``{}`` module:".format(module))
        lines.append("")
        for name in names:
            lines.append(".. autoclass:: safecor.{}".format(name))
            lines.append("   :members:")
            lines.append("   :show-inheritance:")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    groups = collect_classes()
    total = sum(len(names) for names in groups.values())
    print("Classes found: {}".format(total))
    for module, names in groups.items():
        print("  {}: {}".format(module, ", ".join(names)))

    output_file = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "docs",
            "source",
            "api",
            "safecor.generated.rst",
        )
    )
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(generate(groups))
    print("Generated {}".format(output_file))


if __name__ == "__main__":
    main()
