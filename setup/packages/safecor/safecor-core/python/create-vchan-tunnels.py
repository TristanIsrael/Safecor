"""Creates vchan client tunnels between Dom0 and PV/PVH/HVM domains.

For each domain discovered in xenstore, this script starts a vchan-socket-proxy
client that bridges the domain's vchan endpoint to a local UNIX socket. The
resulting sockets are picked up by create-mqtt-tunnels.py for MQTT, and by
the existing input/tty infrastructure.

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


def vchan_endpoint_exists(domid: str, channel: str) -> bool:
    return read_xenstore(f"/local/domain/{domid}/data/vchan/{channel}/ring-ref") != ""


def start_vchan_client(domid: str, channel: str, socket_path: str) -> bool:
    cmd = [
        "vchan-socket-proxy",
        "-m",
        "client",
        domid,
        f"/local/domain/{domid}/data/vchan/{channel}",
        socket_path,
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        SysLogger("create-vchan-tunnels").info(
            f"vchan client started: domid={domid} channel={channel} sock={socket_path}"
        )
        return True
    except FileNotFoundError:
        SysLogger("create-vchan-tunnels").error(
            "vchan-socket-proxy binary not found"
        )
        return False


def main():
    SysLogger("create-vchan-tunnels").info("Starting vchan tunnel manager")
    print("vchan-tunnels: starting discovery loop")

    while True:
        domain_names = list_domain_names()

        for name in domain_names:
            domid = get_domid(name)
            if not domid:
                continue

            channels = ["msg"]
            if name == SYS_USB_NAME:
                channels.extend(SYS_USB_EXTRA_CHANNELS)

            for channel in channels:
                if not vchan_endpoint_exists(domid, channel):
                    continue

                if channel == "msg":
                    socket_path = f"/var/run/safecor/{name}-msg.sock"
                elif channel == "input":
                    socket_path = f"/var/run/safecor/{name}-input.sock"
                elif channel == "tty":
                    socket_path = f"/var/run/safecor/{name}-tty.sock"
                else:
                    continue

                if os.path.exists(socket_path):
                    continue

                start_vchan_client(domid, channel, socket_path)

        time.sleep(VCHAN_POLL_INTERVAL)


if __name__ == "__main__":
    main()
