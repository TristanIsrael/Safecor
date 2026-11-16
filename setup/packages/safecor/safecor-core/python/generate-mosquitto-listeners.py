"""Generates the mosquitto UNIX socket listeners from the product topology.

Writes /etc/mosquitto/conf.d/safecor-listeners.conf with one UNIX listener
per DomU defined in /etc/safecor/topology.json. This file is included by
/etc/mosquitto/mosquitto.conf.

The listeners are named after the domain (not the domid) so they stay valid
when a domain is restarted or recreated with a different domid.

This script is called once at the end of the product installation
(finish-core-init.sh), when the product topology is in place.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os

from safecor import System

OUTPUT_FILE = "/etc/mosquitto/conf.d/safecor-listeners.conf"
SOCKET_TEMPLATE = "/tmp/mqtt-{name}.sock"


def generate_listeners(topology) -> list[str]:
    """Build the mosquitto listener lines for every DomU of the topology.

    Args:
        topology: A Topology object (its `domains` list provides the names).

    Returns:
        The list of mosquitto `listener 0 <socket>` lines, one per DomU.
    """
    return [
        f"listener 0 {SOCKET_TEMPLATE.format(name=domain.name)}"
        for domain in topology.domains
    ]


def write_listeners(output_file: str, lines: list[str]) -> None:
    """Write the generated listeners to the given mosquitto config file."""
    content = [
        "# Generated from /etc/safecor/topology.json by",
        "# generate-mosquitto-listeners.py — do not edit manually.",
    ]
    content.extend(lines)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        f.write("\n".join(content) + "\n")


def main():
    topology = System.get_topology()
    listeners = generate_listeners(topology)
    write_listeners(OUTPUT_FILE, listeners)
    print(f"mosquitto listeners written to {OUTPUT_FILE}: {len(listeners)} domain(s)")


if __name__ == "__main__":
    main()
