#!/bin/sh
# Start the vchan clients (msg, input, tty) in a DomU.
#
# The vchan data is published in the shared xenstore namespace
# /local/domain/system/vchan/<domain>/<channel>: a DomU cannot read
# /local/domain/0, so the channels must not be created in that scope.
#
# The msg channel is a local mosquitto broker: the domain's applications
# connect to the UNIX socket /var/run/safecor/mqtt.sock (the broker
# multiplexes every local client) and the broker's single upstream bridge
# connects to a TCP loopback endpoint created by socat, which spawns one
# vchan-socket-proxy client per accepted connection.
#
# Each daemon is started detached (one pidfile per process) so that the
# service never blocks the boot.
#
# Copyright (c) 2024-2026, Tristan Israël
# Safecor Licence — see python/lib/LICENCE.md

SCRIPT_NAME=$(basename "$0")
MY_NAME=$(hostname)

# Loopback TCP endpoint of the mosquitto bridge (mosquitto -> socat -> vchan).
MQTT_BRIDGE_PORT=18860
BROKER_SOCK="/var/run/safecor/mqtt.sock"

logger -t "Safecor/$SCRIPT_NAME" -p user.info "Starting vchan clients..."

# The DomUs have no loopback interface by default and the mosquitto bridge
# connects to 127.0.0.1, so bring lo up first.
if ! ifconfig lo 127.0.0.1 netmask 255.0.0.0 up 2>/dev/null; then
    ip link set lo up 2>/dev/null \
        || logger -t "Safecor/$SCRIPT_NAME" -p user.err "Cannot bring up the loopback interface"
fi

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

# Start the local MQTT broker for the msg channel.
#
# mosquitto and socat are apk dependencies of this package, so they are
# installed before the post-install runs this script. The wait below is a
# defensive safety net (e.g. a package installed without its dependencies).
start_msg_broker() {
    for i in $(seq 1 60); do
        if [ -x /usr/sbin/mosquitto ] && [ -x /usr/bin/socat ] && id mosquitto >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if [ ! -x /usr/sbin/mosquitto ] || [ ! -x /usr/bin/socat ]; then
        logger -t "Safecor/$SCRIPT_NAME" -p user.err "mosquitto or socat is not installed, the msg channel is unavailable"
        return 1
    fi

    # The broker runs as the mosquitto user and must be able to create its
    # socket in /var/run/safecor.
    chown mosquitto /var/run/safecor

    # socat creates the TCP endpoint of the bridge. Every accepted
    # connection spawns a vchan-socket-proxy client in stdio mode, i.e. one
    # vchan connection per bridge (re)connection.
    start-stop-daemon --start --background --make-pidfile \
        --pidfile "/var/run/safecor/vchan-msg-socat.pid" \
        --exec /usr/bin/socat \
        -- "TCP-LISTEN:$MQTT_BRIDGE_PORT,bind=127.0.0.1,fork,reuseaddr" \
           "EXEC:/usr/bin/vchan-socket-proxy -m client 0 /local/domain/system/vchan/$MY_NAME/msg -"

    # Local broker configuration: a UNIX listener for the domain's
    # applications and a single upstream bridge to the socat endpoint.
    # It is domain specific (the bridge name embeds the domain name), so it
    # is generated at boot in the package's etc directory.
    cat > /usr/lib/safecor/etc/mosquitto.conf <<EOF
log_dest syslog
allow_anonymous true
listener 0 $BROKER_SOCK
connection safecor-$MY_NAME-bridge
remote_clientid safecor-$MY_NAME-bridge
address 127.0.0.1:$MQTT_BRIDGE_PORT
topic # both 0
notifications false
EOF

    start-stop-daemon --start --background --make-pidfile \
        --pidfile "/var/run/safecor/mosquitto-domu.pid" \
        --user mosquitto --group mosquitto \
        --exec /usr/sbin/mosquitto \
        -- -c /usr/lib/safecor/etc/mosquitto.conf

    # The broker creates $BROKER_SOCK as mosquitto:mosquitto, so the
    # domain's svc-* users cannot connect to it. Once the socket exists,
    # make it accessible to the safecor group.
    for i in $(seq 1 20); do
        [ -S "$BROKER_SOCK" ] && break
        sleep 0.5
    done
    if [ -S "$BROKER_SOCK" ]; then
        chgrp safecor "$BROKER_SOCK"
        chmod 660 "$BROKER_SOCK"
    else
        logger -t "Safecor/$SCRIPT_NAME" -p user.err "Broker socket $BROKER_SOCK was not created (channel msg)"
        return 1
    fi
    logger -t "Safecor/$SCRIPT_NAME" -p user.info "Local MQTT broker started (sock=$BROKER_SOCK, bridge=127.0.0.1:$MQTT_BRIDGE_PORT)"
}

# Start one vchan client per remaining channel (input, tty), detached, with
# its own pidfile.
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

start_msg_broker

if [ "$MY_NAME" = "sys-usb" ]; then
    start_vchan_client input /var/run/safecor/input.sock
    start_vchan_client tty /var/run/safecor/tty.sock
fi

logger -t "Safecor/$SCRIPT_NAME" -p user.info "vchan setup complete"
exit 0
