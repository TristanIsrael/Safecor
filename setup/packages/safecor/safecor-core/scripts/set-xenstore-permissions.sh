#!/bin/sh

set -e

xenstore-chmod -r /local/domain/system r

logger -s -t "Safecor/core" -p user.info "Successfully set the Xenstore permissions"
