#!/usr/bin/env python3
"""Script to display conf.py content lines."""
with open('/Users/tristanisrael/Documents/Sources/Safecor/python/lib/docs/source/conf.py', 'r') as f:
    lines = f.readlines()

print(f"Line {48} to {62}:")
for i, line in enumerate(lines[47:63], start=48):
    print(i, line)
