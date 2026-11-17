#!/bin/sh
# Start the vchan clients (msg, input, tty) in a DomU.
#
# The vchan data is published in the shared xenstore namespace
# /local/domain/system/vchan/<domain>/<channel>: a DomU cannot read
# /local/domain/0, so the channels must not be created in that scope.
#
# Each vchan client is started detached (one pidfile per channel) so that
# the service never blocks the boot.
#
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md

SCRIPT_NAME=$(basename "$0")
MY_NAME=$(hostname)

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting vchan clients..."

MY_DOMID=""
for i in $(seq 1 30); do
    MY_DOMID=$(xenstore-read /local/domain/system/domids/$MY_NAME 2>/dev/null)
    [ -n "$MY_DOMID" ] && break
    sleep 1
done

if [ -z "$MY_DOMID" ]; then
    logger -t "Safecor/$SCRIPT_NAME" -p user.err "Cannot discover domid for $MY_NAME"
    exit 1
fi

mkdir -p /var/run/safecor

# Wait for the Dom0 vchan servers to publish the channel data in the shared
# xenstore namespace. The Dom0 starts a server for each channel as soon as
# the domain is registered in /local/domain/system/domids, so this should
# only take a few seconds.
for i in $(seq 1 15); do
    if xenstore-read /local/domain/system/vchan/$MY_NAME/msg/ring-ref >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! xenstore-read /local/domain/system/vchan/$MY_NAME/msg/ring-ref >/dev/null 2>&1; then
    logger -t "Safecor/$SCRIPT_NAME" -p user.err "Dom0 vchan server not found, starting clients anyway"
fi

# Start one vchan client per channel, detached, with its own pidfile.
#
# vchan-socket-proxy creates its UNIX socket as root with mode 0755
# (it never chmods it), so the domain's svc-* users cannot connect to
# it. Once the socket exists, make it accessible to the safecor group.
start_vchan_client() {
    channel="$1"
    sock="$2"
    start-stop-daemon --start --background --make-pidfile \
        --pidfile "/var/run/safecor/vchan-${channel}.pid" \
        --exec /usr/bin/vchan-socket-proxy \
        -- -m client 0 "/local/domain/system/vchan/$MY_NAME/$channel" "$sock"
    for i in $(seq 1 20); do
        [ -S "$sock" ] && break
        sleep 0.5
    done
    if [ -S "$sock" ]; then
        chgrp safecor "$sock"
        chmod 660 "$sock"
    else
        logger -t "Safecor/$SCRIPT_NAME" -p user.err "Socket $sock was not created (channel $channel)"
    fi
    logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan $channel client started (domid=$MY_DOMID, sock=$sock)"
}

start_vchan_client msg /var/run/safecor/mqtt.sock

if [ "$MY_NAME" = "sys-usb" ]; then
    start_vchan_client input /var/run/safecor/input.sock
    start_vchan_client tty /var/run/safecor/tty.sock
fi

logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan setup complete"
exit 0
