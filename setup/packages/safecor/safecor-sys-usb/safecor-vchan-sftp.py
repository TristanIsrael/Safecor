"""Starts the per-DomU vchan+SFTP channels on sys-usb for direct USB mount.

Queries the topology via MQTT to find the domains with direct_mount enabled,
then starts, for each of them:
- a vchan-socket-proxy server bridging the SFTP vchan channel to a UNIX
  socket,
- a socat bridge from that socket to the chrooted sftp-server.

Runs detached (started by the safecor-vchan-sftp service) and retries the
topology query until MQTT is available, so that the boot is never blocked.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import subprocess
import sys
import threading
import time

sys.path.insert(0, "/usr/lib/safecor")

from safecor import Api, MqttFactory, Topics

QUERY_RETRIES = 15
QUERY_TIMEOUT = 10  # seconds, per MQTT query attempt
RETRY_INTERVAL = 5  # seconds between query attempts
DOMAIN_WAIT_TIMEOUT = 60  # seconds to wait for a domain's domid


def log(message: str) -> None:
    print(f"safecor-vchan-sftp: {message}", flush=True)


def query_direct_mount_domains() -> list[str] | None:
    """Query the topology via MQTT for the direct_mount domains.

    Returns:
        The names of the domains with direct_mount enabled, or None if the
        query failed (MQTT not available or no response).
    """
    result = [None]
    event = threading.Event()

    def on_ready():
        Api().subscribe(f"{Topics.MY_CONFIG}/response")
        Api().publish(f"{Topics.MY_CONFIG}/request", {})

    def on_message(topic, payload):
        if topic == f"{Topics.MY_CONFIG}/response":
            result[0] = payload
            event.set()

    mqtt_client = MqttFactory.create_mqtt_client_domu("safecor-vchan-sftp")
    Api().add_ready_callback(on_ready)
    Api().add_message_callback(on_message)
    Api().start(mqtt_client)
    try:
        if not event.wait(timeout=QUERY_TIMEOUT):
            return None
        if result[0] is None:
            return None
        return [
            d["name"] for d in result[0].get("domains", []) if d.get("direct_mount")
        ]
    finally:
        Api().stop()


def wait_for_domid(name: str) -> str:
    """Poll xenstore for the domain's domid with a timeout.

    Returns:
        The domid as a string, or an empty string if not found in time.
    """
    deadline = time.time() + DOMAIN_WAIT_TIMEOUT
    while time.time() < deadline:
        try:
            result = subprocess.run(
                ["xenstore-read", f"/local/domain/system/domids/{name}"],
                capture_output=True,
                text=True,
                check=True,
            )
            domid = result.stdout.strip()
            if domid:
                return domid
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        time.sleep(2)
    return ""


def start_channel(name: str, domid: str) -> None:
    """Start the vchan server and the socat bridge for one domain.

    The SFTP vchan channel data is shared in the xenstore namespace
    /local/domain/system/vchan/<domain>/<channel>, readable by all DomUs.
    """
    vchan_sock = f"/var/run/safecor/vchan-{name}.sock"
    vchan_path = f"/local/domain/system/vchan/{name}/sftp"

    subprocess.run(
        [
            "start-stop-daemon",
            "--start",
            "--background",
            "--make-pidfile",
            "--pidfile",
            f"/var/run/safecor/vchan-{name}.pid",
            "--exec",
            "/usr/bin/vchan-socket-proxy",
            "--",
            "-m",
            "server",
            domid,
            vchan_path,
            vchan_sock,
        ],
        check=True,
    )
    subprocess.run(
        [
            "start-stop-daemon",
            "--start",
            "--background",
            "--make-pidfile",
            "--pidfile",
            f"/var/run/safecor/socat-{name}.pid",
            "--exec",
            "/usr/bin/socat",
            "--",
            f"UNIX-LISTEN:{vchan_sock},fork",
            'EXEC:"chroot /media /usr/lib/ssh/sftp-server"',
        ],
        check=True,
    )


def main() -> None:
    log("starting")

    domains = None
    for attempt in range(1, QUERY_RETRIES + 1):
        domains = query_direct_mount_domains()
        if domains is not None:
            break
        log(f"topology query failed (attempt {attempt}/{QUERY_RETRIES})")
        if attempt < QUERY_RETRIES:
            time.sleep(RETRY_INTERVAL)

    if domains is None:
        log("error: failed to query topology via MQTT")
        sys.exit(1)

    if not domains:
        log("no domains with direct_mount found in topology")
        return

    for name in domains:
        domid = wait_for_domid(name)
        if not domid:
            log(f"warning: no domid found for domain {name}, skipping")
            continue
        log(f"starting vchan SFTP channel for {name} (domid {domid})")
        start_channel(name, domid)

    log("vchan SFTP channels started")


if __name__ == "__main__":
    main()
