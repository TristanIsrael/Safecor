#!/bin/sh
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

# Wait for Dom0 vchan server to be ready
logger -t "Safecor/$SCRIPT_NAME" -p user.info "Waiting for Dom0 vchan server (domid=$MY_DOMID)..."
for i in $(seq 1 60); do
    if xenstore-read /local/domain/0/data/vchan/$MY_DOMID/msg/ring-ref >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! xenstore-read /local/domain/0/data/vchan/$MY_DOMID/msg/ring-ref >/dev/null 2>&1; then
    logger -t "Safecor/$SCRIPT_NAME" -p user.err "Dom0 vchan server not found, starting client anyway"
fi

vchan-socket-proxy -m client 0 /local/domain/0/data/vchan/$MY_DOMID/msg /var/run/safecor/mqtt.sock &
VCHAN_MSG_PID=$!
logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan msg client started (domid=$MY_DOMID, pid=$VCHAN_MSG_PID)"

if [ "$MY_NAME" = "sys-usb" ]; then
    vchan-socket-proxy -m client 0 /local/domain/0/data/vchan/$MY_DOMID/input /var/run/safecor/input.sock &
    VCHAN_INPUT_PID=$!
    logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan input client started (pid=$VCHAN_INPUT_PID)"

    vchan-socket-proxy -m client 0 /local/domain/0/data/vchan/$MY_DOMID/tty /var/run/safecor/tty.sock &
    VCHAN_TTY_PID=$!
    logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan tty client started (pid=$VCHAN_TTY_PID)"
fi

echo "$VCHAN_MSG_PID" > /var/run/safecor-vchan.pid
logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan setup complete"

wait $VCHAN_MSG_PID
