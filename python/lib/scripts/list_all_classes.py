#!/usr/bin/env python3
"""Generate a complete sidebar list of all safecor classes for the Furo theme."""

import ast
import os

def find_classes_in_file(filepath):
    """Extract all public class names from a Python file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
        return classes
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return []

# Walk the safecor directory
base_path = '/Users/tristanisrael/Documents/Sources/Safecor/python/lib/src/safecor'

all_classes = []
for root, dirs, files in os.walk(base_path):
    for filename in files:
        if filename.endswith('.py'):
            filepath = os.path.join(root, filename)
            classes = find_classes_in_file(filepath)
            all_classes.extend(classes)

# Remove duplicates and filter out private classes (starting with _)
all_classes = sorted(set([c for c in all_classes if not c.startswith('_')]))

# Print to stdout so it can be redirected to file or used directly
for name in all_classes:
    print(name)
