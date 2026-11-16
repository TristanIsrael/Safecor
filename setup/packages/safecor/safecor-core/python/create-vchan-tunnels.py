"""Creates vchan server tunnels between Dom0 and PV/PVH/HVM domains.

For each domain discovered in xenstore, this script starts a vchan-socket-proxy
server that bridges the domain's vchan channel to a local UNIX socket. The
msg channel connects directly to a Mosquitto broker socket. The input and tty
channels (sys-usb only) connect to their respective local sockets.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import subprocess
import time

from safecor import SysLogger

VCHAN_POLL_INTERVAL = 1
XENSTORE_DOMIDS_PATH = "/local/domain/system/domids"
SYS_USB_NAME = "sys-usb"
SYS_USB_EXTRA_CHANNELS = ["input", "tty"]


def read_xenstore(path: str) -> str:
    try:
        result = subprocess.run(
            ["xenstore-read", path], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def list_domain_names() -> list[str]:
    try:
        result = subprocess.run(
            ["xenstore-ls", XENSTORE_DOMIDS_PATH],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def get_domid(domain_name: str) -> str:
    return read_xenstore(f"{XENSTORE_DOMIDS_PATH}/{domain_name}")


def get_socket_path(channel: str, domid: str) -> str:
    if channel == "msg":
        return f"/tmp/mqtt_msg_{domid}.sock"
    if channel == "input":
        return "/var/run/safecor/sys-usb-input.sock"
    if channel == "tty":
        return "/var/run/safecor/sys-usb-tty.sock"
    return ""


def start_vchan_server(
    domid: str, channel: str, socket_path: str
) -> subprocess.Popen | None:
    if not os.path.exists(socket_path):
        return None

    cmd = [
        "vchan-socket-proxy",
        "-m",
        "server",
        domid,
        f"/local/domain/0/data/vchan/{domid}/{channel}",
        socket_path,
    ]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        SysLogger("create-vchan-tunnels").info(
            f"vchan server started: domid={domid} channel={channel} sock={socket_path}"
        )
        return proc
    except FileNotFoundError:
        SysLogger("create-vchan-tunnels").error("vchan-socket-proxy binary not found")
        return None


def stop_server(proc: subprocess.Popen):
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    except OSError:
        pass


def main():
    SysLogger("create-vchan-tunnels").info("Starting vchan tunnel manager")
    print("vchan-tunnels: starting discovery loop")

    # Track active vchan server processes: {(domid, channel): Popen}
    active_servers: dict[tuple[str, str], subprocess.Popen] = {}

    while True:
        domain_names = list_domain_names()
        current: dict[tuple[str, str], tuple[str, str, str]] = {}

        for name in domain_names:
            domid = get_domid(name)
            if not domid:
                continue

            channels = ["msg"]
            if name == SYS_USB_NAME:
                channels.extend(SYS_USB_EXTRA_CHANNELS)

            for channel in channels:
                current[(domid, channel)] = (name, domid, channel)

        # Stop servers for domains that no longer exist or changed domid
        for key in list(active_servers.keys()):
            if key not in current:
                SysLogger("create-vchan-tunnels").info(
                    f"Stopping vchan server: domid={key[0]} channel={key[1]}"
                )
                stop_server(active_servers[key])
                del active_servers[key]

        # Start servers for newly discovered domains
        for key, (name, domid, channel) in current.items():
            if key not in active_servers:
                socket_path = get_socket_path(channel, domid)
                if not socket_path:
                    continue
                proc = start_vchan_server(domid, channel, socket_path)
                if proc is not None:
                    active_servers[key] = proc
                elif not os.path.exists(socket_path):
                    SysLogger("create-vchan-tunnels").info(
                        f"Socket not ready for domid={domid} channel={channel}, "
                        f"will retry: {socket_path}"
                    )

        time.sleep(VCHAN_POLL_INTERVAL)


if __name__ == "__main__":
    main()
