"""Enable the safecor_emulator pytest plugin for these tests.

A product test suite does the same in its own conftest.py.
"""

pytest_plugins = ["safecor_emulator.pytest_plugin"]
