#!/bin/sh
# Reboot a Domain and update its domid in xenstore.
#
# The hypervisor destroys and recreates the domain on reboot, so the domain
# comes back with a new domid. This script waits for the domain to go down,
# then for it to come back with a new domid, and only then writes the new
# domid to xenstore: the Dom0 vchan discovery loop (create-vchan-tunnels.py)
# recreates the vchan servers when the domid changes, so a stale or missing
# write would leave the restarted domain without any vchan (issue #262).
#
# The polling windows and interval can be overridden for testing with the
# DOWN_TIMEOUT, UP_TIMEOUT and POLL_INTERVAL environment variables.
#
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md

SCRIPT_NAME=$(basename "$0")
DOWN_TIMEOUT=${DOWN_TIMEOUT:-30}  # seconds to wait for the domain to go down
UP_TIMEOUT=${UP_TIMEOUT:-60}  # seconds to wait for the domain to come back
POLL_INTERVAL=${POLL_INTERVAL:-2}

get_domid() {
    xl info "$1" 2>/dev/null | grep -w ID | awk '{print $3}'
}

old_domid=$(get_domid "$1")

if ! /usr/sbin/xl reboot "$1"; then
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Failed to reboot $1"
    exit 1
fi

# Wait for the domain to go down (it is destroyed on reboot)
deadline=$(( $(date +%s) + DOWN_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    [ -z "$(get_domid "$1")" ] && break
    sleep "$POLL_INTERVAL"
done

# Wait for the domain to come back with a new domid
new_domid=""
deadline=$(( $(date +%s) + UP_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    new_domid=$(get_domid "$1")
    [ -n "$new_domid" ] && [ "$new_domid" != "$old_domid" ] && break
    sleep "$POLL_INTERVAL"
done

if [ -n "$new_domid" ] && [ "$new_domid" != "$old_domid" ]; then
    xenstore-write /local/domain/system/domids/$1 "$new_domid"
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.debug "Domain $1 new domid $new_domid written to xenstore (old domid ${old_domid:-unknown})"
else
    logger -s -t "Safecor/$SCRIPT_NAME" -p user.err "Failed to get a new domid for $1 after reboot (old domid ${old_domid:-unknown})"
    exit 1
fi
