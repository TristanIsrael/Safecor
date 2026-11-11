"""Writes screen resolution and rotation to Xenstore so DomUs can query display parameters.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import subprocess
import sys

from safecor import SysLogger, System

if __name__ == "__main__":
    SysLogger("write-screen-information-to-xenstore").info(
        "Write screen information into Xenstore..."
    )

    topology = System.get_topology()

    if not topology.screen.enabled:
        SysLogger("write-screen-information-to-xenstore").info(
            "The screen is disabled in the topology"
        )
        sys.exit(0)

    command = f"xenstore-write /local/domain/system/screen_rotation {topology.screen.rotation}"
    subprocess.run(command, shell=True, check=True)

    SysLogger("write-screen-information-to-xenstore").info("... done")
