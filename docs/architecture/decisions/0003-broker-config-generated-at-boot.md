# 0003 — The DomU broker configuration is generated at boot

**Status**: Accepted (v2)

## Context

With one local broker per DomU ([0001](0001-per-domu-local-mqtt-broker.md)), the broker's upstream bridge needs a **connection name that embeds the domain name** (`safecor-<domain>-bridge`) and a fixed loopback address. A static, packaged `mosquitto.conf` cannot express the per-domain value, and shipping one file per domain would duplicate content across packages.

## Decision

The broker configuration is **generated at boot** by `setup-vchan.sh` (the `setup-vchan` OpenRC service, default runlevel) in `/usr/lib/safecor/etc/mosquitto.conf`, then the local broker is started with that file. The file is **not** part of any package.

## Consequences

- The `setup-vchan.sh` 60 s wait loop is only a **safety net**: `mosquitto` and `socat` are apk dependencies of `safecor-domu-base`, so they are present before post-install runs (issue #258).
- The APKBUILD checksums never include the broker configuration (generated content, not packaged content).
- The domain's identity (its own name) is the only input needed — no cross-domain information is required at boot.
