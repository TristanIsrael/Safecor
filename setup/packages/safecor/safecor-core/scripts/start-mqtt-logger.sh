#!/bin/sh

SCRIPT_NAME=$(basename "$0")
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting mosquitto degugging..."

mkdir -p /var/log/safecor
rm -f /var/log/safecor/messages.log

mosquitto_sub -t "#" -v | while IFS= read -r line; do
    printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$line"
done >> /var/log/safecor/messages.log

logger -t "Safecor/$SCRIPT_NAME" -p user.warn "Mosquito debugging has finished"
