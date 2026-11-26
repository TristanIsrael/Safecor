"""Creates vchan server tunnels between Dom0 and PV/PVH/HVM domains.

For each domain discovered in xenstore, this script starts a vchan-socket-proxy
server that bridges the domain's vchan channel to a local UNIX socket. The
msg channel connects directly to a Mosquitto broker socket. The input and tty
channels (sys-usb only) connect to their respective local sockets.

All XenStore access goes through the ``safecor`` library's ``XenStore`` class
(libxenstore bindings): no ``xenstore-*`` subprocesses and no ``doas`` grant
are needed — the ``svc-vchan-tunnels`` user has read/write access to the
``/local/domain/system`` subtree (``set-xenstore-permissions.sh``, ADR 0006).

The domid cache at ``/local/domain/system/domids/<name>`` is demoted to a
self-healed convenience cache (see ADR 0006): the discovery loop always
resolves the **live** domid from the Xen tree ``/local/domain/<N>/name``,
uses it for the vchan servers, and writes it back to the cache only when it
differs from the cached value.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import subprocess
import time
from typing import TextIO

from safecor import SysLogger, XenStore

VCHAN_POLL_INTERVAL = 1
LOCAL_DOMAIN_PATH = "/local/domain"
XENSTORE_DOMIDS_PATH = "/local/domain/system/domids"
SYS_USB_NAME = "sys-usb"
SYS_USB_EXTRA_CHANNELS = ["input", "tty"]
# Standard error of every vchan server is appended to this file so that a
# startup failure (e.g. missing /dev/xen/gntalloc access) is visible in the logs.
SERVER_LOG_PATH = "/var/log/safecor/vchan-servers.log"


def list_domain_names(store: "XenStore | None" = None) -> list[str]:
    """List the domain names from the domid convenience cache.

    The cache is flat: every child of ``/local/domain/system/domids`` is a
    domain name (equivalent of ``xenstore-ls`` on that path).
    """
    store = store or XenStore()
    return [name for name in store.read_children(XENSTORE_DOMIDS_PATH) if name]


def get_domid(domain_name: str, store: "XenStore | None" = None) -> str:
    """Return the cached domid for *domain_name* (from the convenience cache)."""
    store = store or XenStore()
    cached = store.read_path(f"{XENSTORE_DOMIDS_PATH}/{domain_name}")
    return cached.strip() if cached else ""


# ---------------------------------------------------------------------------
# Live domid resolution (ADR 0006 — cache demoted to self-healed convenience)
# ---------------------------------------------------------------------------


def resolve_live_domid(domain_name: str, store: "XenStore | None" = None) -> str:
    """Resolve the live domid for *domain_name* from the Xen tree.

    Enumerates the children of ``/local/domain`` and reads each
    ``<N>/name``; the first match is the live domid (hypervisor-maintained,
    unforgeable).  If the resolved domid differs from the cached value, the
    cache is updated in place.

    Returns:
        The live domid (string), or ``""`` if not found.
    """
    store = store or XenStore()
    try:
        domids = store.read_children(LOCAL_DOMAIN_PATH)
    except OSError:
        return ""

    for domid in domids:
        actual_name = store.read_path(f"{LOCAL_DOMAIN_PATH}/{domid}/name")
        if actual_name != domain_name:
            continue

        cached = get_domid(domain_name, store)
        if should_write_back(cached, domid):
            if store.write("system", f"domids/{domain_name}", domid):
                SysLogger("create-vchan-tunnels").info(
                    f"domid {cached} -> {domid} (self-heal for {domain_name})"
                )
            else:
                SysLogger("create-vchan-tunnels").warn(
                    f"domid cache self-heal failed for {domain_name} "
                    f"(cache keeps {cached or 'no value'} until the next "
                    "iteration)"
                )
        return domid
    return ""


def should_write_back(old_domid: str, new_domid: str) -> bool:
    """Return True when the domid has changed and the cache must be updated."""
    return bool(old_domid) and bool(new_domid) and old_domid != new_domid


def get_socket_path(channel: str, name: str) -> str:
    if channel == "msg":
        return f"/tmp/mqtt-{name}.sock"
    if channel == "input":
        return "/var/run/safecor/sys-usb-input.sock"
    if channel == "tty":
        return "/var/run/safecor/sys-usb-tty.sock"
    return ""


def get_vchan_path(name: str, channel: str) -> str:
    # The vchan data lives in the shared xenstore namespace, which is readable
    # by all DomUs (DomUs cannot read /local/domain/0).
    return f"/local/domain/system/vchan/{name}/{channel}"


def start_vchan_server(
    domid: str, name: str, channel: str, socket_path: str, server_log: TextIO
) -> subprocess.Popen | None:
    if not os.path.exists(socket_path):
        return None

    cmd = [
        "vchan-socket-proxy",
        "-m",
        "server",
        domid,
        get_vchan_path(name, channel),
        socket_path,
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=server_log)
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


def reap_dead_servers(
    active_servers: dict[tuple[str, str], subprocess.Popen],
) -> list[tuple[str, str]]:
    """Reap the vchan servers that have exited.

    A server that has exited (for instance a ``libxenvchan_server_init``
    failure) is removed from the tracking dictionary so that the discovery
    loop restarts it on the next iteration.  Waiting on the process also
    clears the zombie process.

    Returns:
        The list of (domid, channel) keys that were removed.
    """
    removed: list[tuple[str, str]] = []
    for key in list(active_servers.keys()):
        proc = active_servers[key]
        exit_code = proc.poll()
        if exit_code is not None:
            proc.wait()
            SysLogger("create-vchan-tunnels").error(
                f"vchan server exited: domid={key[0]} channel={key[1]} "
                f"exit_code={exit_code} — see {SERVER_LOG_PATH} — will restart"
            )
            del active_servers[key]
            removed.append(key)
    return removed


def main():
    SysLogger("create-vchan-tunnels").info("Starting vchan tunnel manager")
    print("vchan-tunnels: starting discovery loop")

    # A single XenStore connection for the whole discovery loop.
    store = XenStore()

    # Every vchan server inherits this handle for its standard error so that
    # a startup failure is logged instead of being lost.
    server_log = open(SERVER_LOG_PATH, "a")

    # Track active vchan server processes: {(domid, channel): Popen}
    active_servers: dict[tuple[str, str], subprocess.Popen] = {}
    # Track (name, channel) pairs for which a missing socket was already logged
    logged_missing_sockets: set[tuple[str, str]] = set()

    while True:
        # The whole iteration is fault-tolerant (the old CLI contract): a
        # failing xenstore read must not kill the loop, nor stop the running
        # servers — the next iteration converges again.
        try:
            # Reap the servers that have exited so that they are restarted.
            reap_dead_servers(active_servers)

            domain_names = list_domain_names(store)
            current: dict[tuple[str, str], tuple[str, str, str]] = {}

            for name in domain_names:
                # Always resolve the live domid (ADR 0006): the convenience
                # cache is self-healed when a difference is detected.
                domid = resolve_live_domid(name, store)
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
                    socket_path = get_socket_path(channel, name)
                    if not socket_path:
                        continue
                    proc = start_vchan_server(
                        domid, name, channel, socket_path, server_log
                    )
                    if proc is not None:
                        active_servers[key] = proc
                    elif not os.path.exists(socket_path) and (name, channel) not in (
                        logged_missing_sockets
                    ):
                        logged_missing_sockets.add((name, channel))
                        if channel == "msg":
                            SysLogger("create-vchan-tunnels").error(
                                f"No mosquitto listener for domain {name} at "
                                f"{socket_path} — regenerate "
                                f"/etc/mosquitto/conf.d/safecor-listeners.conf "
                                f"from the topology"
                            )
                        else:
                            SysLogger("create-vchan-tunnels").info(
                                f"Socket not ready for domain={name} "
                                f"channel={channel}, will retry: {socket_path}"
                            )
        except Exception as e:
            SysLogger("create-vchan-tunnels").error(
                f"Discovery iteration failed (xenstore connection issue?): "
                f"{e} — retrying"
            )

        time.sleep(VCHAN_POLL_INTERVAL)


if __name__ == "__main__":
    main()
