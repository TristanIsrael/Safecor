#!/bin/sh
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md


SCRIPT_NAME=$(basename "$0")
logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "Setting Xenstore permissions..."

xenstore-chmod -r /local/domain/system r

logger -s -t "Safecor/$SCRIPT_NAME" -p user.info "... done"
