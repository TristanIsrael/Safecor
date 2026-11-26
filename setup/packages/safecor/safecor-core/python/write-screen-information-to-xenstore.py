"""Writes the screen rotation to Xenstore so DomUs can query display parameters.

The screen size is written by the orchestrator's initd as a boot-time one-shot
shell command (NFR-4 scopes the ``XenStore`` class rule to Python code).

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from safecor import SysLogger, System, XenStore


def main() -> None:
    SysLogger("write-screen-information-to-xenstore").info(
        "Write screen information into Xenstore..."
    )

    topology = System.get_topology()

    if not topology.screen.enabled:
        SysLogger("write-screen-information-to-xenstore").info(
            "The screen is disabled in the topology"
        )
        return

    XenStore().write("system", "screen_rotation", str(topology.screen.rotation))

    SysLogger("write-screen-information-to-xenstore").info("... done")


if __name__ == "__main__":
    main()
