#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Setting Xenstore permissions..."

xenstore-chmod -r /local/domain/system r

logger -t "Safecor/$SCRIPT_NAME" -p user.info "... done"
