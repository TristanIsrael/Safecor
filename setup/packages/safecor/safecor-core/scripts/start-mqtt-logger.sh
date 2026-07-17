#!/bin/sh

set -e
logger -s -t "Safecor/core" -p user.notice "Starting messaging logging into messages.log"

mkdir -p /var/log/safecor
rm -f /var/log/safecor/messages.log

mosquitto_sub -t "#" -v | while IFS= read -r line; do
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$line"
done >> /var/log/safecor/messages.log

logger -s -t "Safecor/core" -p user.warn "The messaging logging has finished"
