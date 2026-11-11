""" Generates the Xorg monitor configuration (resolution and rotation) from the Safecor topology.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import json
from safecor import SysLogger, System


def angle_to_rotate(angle):
    "Translates a rotation angle (0, 90, -90, 180) to the corresponding Xorg rotation value."
    mapping = {
        0: "normal",
        90: "left",
        -90: "right",
        180: "inverted"
    }
    return mapping.get(angle, "normal")


def write_monitor_section(angle:int) -> None:
    "Writes the Xorg monitor configuration file with resolution and rotation settings."
    filepath = "/etc/X11/xorg.conf.d/10-monitor.conf"

    # Read current resolution
    with open('/sys/class/graphics/fb0/virtual_size', 'r') as fichier:
        resolution = fichier.read().strip().replace(",", "x")
        #print(resolution)

    # Calculate resolution
    if resolution is None:
        resolution = "1024x768"

    # Apply rotation
    section = f"""
Section "Monitor"
    Identifier "Monitor0"
    Option "PreferredMode" "{resolution}"
    Option "Rotate" "{angle_to_rotate(angle)}"
    Option "DPMS" "false"
EndSection
"""
            
    with open(filepath, "w") as fichier:
        fichier.write(section)

if __name__ == "__main__":
    SysLogger("Generate X config").info("Generating X server configuration files...")

    topology = System.get_topology()
    rotation = topology.screen.rotation
               
    write_monitor_section(rotation)
    
    SysLogger("Generate X config").info("... done")