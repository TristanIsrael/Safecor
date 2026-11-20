# 0001 — One local Mosquitto broker per DomU

**Status**: Accepted (v2)

## Context

In v1, every application of a DomU connected to the Dom0 broker over the vchan `msg` channel (one shared, point-to-point link per domain). This broke as soon as a domain hosted **several** MQTT clients (core services + product applications + the direct-mount manager): the vchan-socket-proxy bridge was not multiplexing local clients, and a broken link took down every client of the domain.

## Decision

Each DomU runs its **own local Mosquitto broker**:

- Every local client (the domain's applications, the core services, the direct-mount manager) connects to the broker's UNIX socket `/var/run/safecor/mqtt.sock`; the broker **multiplexes** them.
- A single **upstream bridge** (connection `safecor-<domain>-bridge`, topic `#`, QoS 0) carries the domain's traffic to the Dom0 central broker over the vchan `msg` channel: bridge → TCP `127.0.0.1:18860` → socat → `vchan-socket-proxy` client (stdio) → Dom0 vchan server → `/tmp/mqtt-<domain>.sock`.

This makes the local side robust: any number of local clients, and a bridge reconnection only re-spawns the vchan-socket-proxy process.

## Consequences

- `mosquitto` and `socat` are **apk dependencies** of `safecor-domu-base` (installed before the local broker starts — issue #258).
- The bridge name embeds the domain name → the broker configuration cannot be a packaged file (see [0003](0003-broker-config-generated-at-boot.md)).
- The loopback interface is brought up by `setup-vchan.sh` (the DomUs have no network interface by default).
- A product now **can** run several MQTT clients in the same domain; the product's own broker is never needed.

See [../components/messaging.md](../components/messaging.md) for the end-to-end Low Level Design.
