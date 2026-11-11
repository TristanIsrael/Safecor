#!/usr/bin/env python3
""" Launcher for the DirectMountManager process. """

import sys
sys.path.insert(0, "/usr/lib/safecor")

from safecor import DirectMountManager

if __name__ == "__main__":
    manager = DirectMountManager()
    manager.run()
