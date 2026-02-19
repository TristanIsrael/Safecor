#!/bin/sh

cd /usr/lib/safecor/tests/src/tests
DISPLAY=:0 /usr/bin/python3 main.py -platform xcb 
