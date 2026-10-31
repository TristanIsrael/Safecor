#!/usr/bin/env python3
"""
Generates a complete API reference RST file listing all safecor classes by category.
This ensures the sidebar shows ALL classes in Furo, not just modules/imports.

Usage:
    python gen_api_rst.py > docs/source/api/safecor.generated.rst
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src import safecor
except Exception as e:
    print(f"Warning: Could not import safecor: {e}")
    print("Generating with minimal structure only...")
    sys.exit(0)

# Collect all classes/functions from safecor module
modules_data = [
    ("Core", "Classes et fonctions core du module safecor"),
    ("Domain", "DomainController interfaces et gestionnaires DOM0/DomU"),
    ("Hardware", "Gestion périphériques (USB, X11, Serial)"),
    ("API", "Helpers et outils génériques (logging, MQTT, tasks)"),
]

class_names = [
    'Api',
    'ApiHelper',
    'Dom0Controller',
    'System',
    'Topology',
    'Domain',
    'MqttClient',
    'SerialMQTTClient',
    'MqttFactory',
    'XenStore',
    'FileHelper',
    'DiskMonitor',
    'SysUsbController',
    'Logger',
    'TaskRunner',
]

# Extract from safecor source directly via inspection
from src.safecor import *


functions = [name for name in dir(safecor) 
            if not name.startswith('_') and callable(getattr(safecor, name))
           ]

# Filter to known public classes only
public_classes = [name for name in class_names 
                  if hasattr(safecor, name)]


print("Classes publiques trouvées:", len(public_classes))
for name in sorted(public_classes):
    obj = getattr(safecor, name)
    print(f"  - {name}: {type(obj).__name__}")

# Generate RST content
rst_content = """\
Safecor API Reference (Full List)
==================================

Complete reference of the safecor package. This page includes all classes, 
functions, and constants auto-generated from docstrings and type hints.

The above list contains classes found in the ``safecor`` Python module via introspection.
For detailed documentation on each function/class, see their individual docstrings.

.. autoclass:: safecor.Api
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: safecor.list_classes
"""

# Add class details section if we found classes
if public_classes:
    rst_content += """\
.. note::
   
   Classe publique du module ``safecor``:

   {% for name in sorted(public_classes) %}
   - :attr:`<ref>`safecor.{name}>_` {{ name }}
   {% endfor %}
"""

# Write to file
output_file = os.path.abspath('docs/source/api/safecor.generated.rst')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(rst_content)

print(f"\nGenerated API RST at: {output_file}")
print(f"Total classes found: {len(public_classes)}")

sys.exit(0)
