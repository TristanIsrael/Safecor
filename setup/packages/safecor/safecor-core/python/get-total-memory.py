""" Prints the total physical memory of the platform in MB (read via xl info).

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import subprocess

def get_total_memory_with_xl():
    "Returns the total physical memory of the platform in kB by parsing xl info output."
    result = subprocess.run(['xl', 'info'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith("total_memory"):
            return int(line.split(':')[1].strip()) * 1024  # Convertir en kB
    return None

memory_kb = get_total_memory_with_xl()
if memory_kb:
    print(round(memory_kb / 1024))
else:
    print(0)
    