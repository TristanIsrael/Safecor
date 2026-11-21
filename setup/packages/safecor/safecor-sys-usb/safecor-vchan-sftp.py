"""Starts the per-DomU vchan+SFTP channels on sys-usb for direct USB mount.

Queries the topology via MQTT to find the domains with direct_mount enabled,
builds the sftp-server chroot under /media/usb, then starts, for each of
those domains:
- a socat bridge from a UNIX socket to the chrooted sftp-server,
- a vchan-socket-proxy server bridging the SFTP vchan channel to that socket.

Runs detached (started by the safecor-vchan-sftp service) and retries the
topology query until MQTT is available, so that the boot is never blocked.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import shutil
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

# The chroot root is /media/usb (the mount tree the client mounts at
# /media/usb), so the chrooted sftp-server serves /media/usb/<disk>/... as
# /<disk>/... to the client.
CHROOT_ROOT = "/media/usb"
SFTP_SERVER = "/usr/lib/ssh/sftp-server"


def log(message: str) -> None:
    print(f"safecor-vchan-sftp: {message}", flush=True)


def parse_direct_mount_domains(response: dict) -> list[tuple[str, str]]:
    """Extract the (name, mode) pairs of the direct_mount domains.

    The mode is "ro" or "rw" (default "rw"). A falsy direct_mount value
    (False, None, an empty dict) means the domain is not enabled, as in the
    DirectMountManager reference. A non-dict truthy value (e.g. a bare
    true) or an invalid mode defaults to "rw".
    """
    pairs = []
    for d in response.get("domains", []):
        dm = d.get("direct_mount")
        if not dm:
            continue
        mode = dm.get("mode", "rw") if isinstance(dm, dict) else "rw"
        if mode not in ("ro", "rw"):
            log(
                f"warning: invalid direct_mount mode {mode!r} for domain "
                f"{d.get('name')!r}, using 'rw'"
            )
            mode = "rw"
        pairs.append((d["name"], mode))
    return pairs


def parse_ldd(output: str) -> list[str]:
    """Extract the shared object paths from the output of ldd(1).

    The shared libraries are the paths after "=>"; the dynamic linker is
    reported as a plain path on its own line.
    """
    paths = []
    for line in output.splitlines():
        line = line.strip()
        if "=>" in line:
            paths.append(line.split("=>", 1)[1].strip().split()[0])
        elif line.startswith("/"):
            paths.append(line.split()[0])
    return paths


def sftp_server_args(mode: str) -> list[str]:
    """The sftp-server command-line arguments for a mount mode.

    -u 077: no group or other permissions on the files sftp-server creates.
    -R: read-only mode (open for write and every state-changing request are
        denied), for ro domains.
    """
    args = ["-u", "077"]
    if mode == "ro":
        args.append("-R")
    return args


def build_chroot() -> bool:
    """Build the sftp-server chroot under /media/usb.

    Copies /usr/lib/ssh/sftp-server and its shared libraries (plus the
    dynamic linker) into the chroot, so that the chrooted sftp-server can
    run. The DomU root is a tmpfs rebuilt at every boot, so the chroot is
    rebuilt at every boot.
    """
    try:
        subprocess.run(["mkdir", "-p", f"{CHROOT_ROOT}/usr/lib/ssh"], check=True)
        shutil.copy2(SFTP_SERVER, f"{CHROOT_ROOT}{SFTP_SERVER}")
        result = subprocess.run(
            ["ldd", SFTP_SERVER], capture_output=True, text=True, check=True
        )
        for lib in parse_ldd(result.stdout):
            if not os.path.isabs(lib):
                continue
            dest = f"{CHROOT_ROOT}{lib}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(lib, dest)
        return True
    except (subprocess.SubprocessError, OSError, shutil.Error) as e:
        log(f"error: failed to build the sftp chroot: {e}")
        return False


def query_direct_mount_domains() -> list[tuple[str, str]] | None:
    """Query the topology via MQTT for the direct_mount domains.

    Returns:
        The (name, mode) pairs of the domains with direct_mount enabled, or
        None if the query failed (MQTT not available or no response).
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
        return parse_direct_mount_domains(result[0])
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


def start_channel(name: str, domid: str, mode: str) -> None:
    """Start the socat bridge and the vchan server for one domain.

    The socat UNIX listener is started first: the vchan server connects to
    the socket that socat creates. The SFTP vchan channel data is shared in
    the xenstore namespace /local/domain/system/vchan/<domain>/sftp,
    readable by all DomUs.
    """
    vchan_sock = f"/var/run/safecor/vchan-{name}.sock"
    vchan_path = f"/local/domain/system/vchan/{name}/sftp"
    sftp_cmd = " ".join(["chroot", CHROOT_ROOT, SFTP_SERVER, *sftp_server_args(mode)])

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
            f'EXEC:"{sftp_cmd}"',
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

    if not build_chroot():
        log("error: the sftp chroot could not be built, aborting")
        sys.exit(1)

    for name, mode in domains:
        domid = wait_for_domid(name)
        if not domid:
            log(f"warning: no domid found for domain {name}, skipping")
            continue
        log(f"starting vchan SFTP channel for {name} (domid {domid}, mode {mode})")
        start_channel(name, domid, mode)

    log("vchan SFTP channels started")


if __name__ == "__main__":
    main()
