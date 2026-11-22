#!/usr/bin/env python3
"""Starts and stops the direct mount SFTP channels on sys-usb (root).

Run as root by the SysUsbController through doas (the controller user is
granted this single command in the doas configuration): the per-session
sftp sandbox (bwrap -> setpriv -> sftp-server) needs a root parent to drop
to the svc-sys-usb-sftp account.

Usage:
    safecor-dm-channels.py '<json spec>'

Spec:
    {"action": "start", "name": "<domain>", "domid": <int>, "mode": "ro"|"rw"}
    {"action": "stop",  "name": "<domain>"}

The channel logic (start-stop-daemon sequence, sftp sandbox) is provided
by the safecor library (see the SFTP section of
safecor._sys_usb_controller): this helper only bridges the privilege
elevation.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import json
import os
import sys

sys.path.insert(0, "/usr/lib/safecor")

from safecor._sys_usb_controller import (  # noqa: E402
    SFTP_ROOT,
    MountMode,
    sandbox_context,
    sftp_credentials,
    start_sftp_channel,
    stop_sftp_channel,
)


def log(message: str) -> None:
    print(f"safecor-dm-channels: {message}", file=sys.stderr, flush=True)


def main() -> int:
    if len(sys.argv) != 2:
        log("usage: safecor-dm-channels.py '<json spec>'")
        return 2

    try:
        spec = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        log(f"invalid JSON spec: {e}")
        return 2

    action = spec.get("action")
    name = spec.get("name")
    if not action or not name:
        log("the spec needs an 'action' and a 'name'")
        return 2

    try:
        if action == "stop":
            stop_sftp_channel(name)
            return 0

        if action == "start":
            domid = spec.get("domid")
            if not isinstance(domid, int):
                log(f"invalid domid for {name}: {domid!r}")
                return 1
            mode = MountMode(spec.get("mode", "rw"))
            # The bind source of the sandbox root must exist at session
            # spawn (mdev creates the per-disk subdirectories).
            os.makedirs(SFTP_ROOT, exist_ok=True)
            # The sandbox drops to this account (see the library's
            # bwrap_args); it is created by the package's post-install
            # script, so a missing account is fatal.
            sftp_uid, sftp_gid = sftp_credentials()
            ctx = sandbox_context(sftp_uid, sftp_gid)
            start_sftp_channel(name, domid, mode, sftp_uid, sftp_gid, ctx)
            return 0

        log(f"unknown action {action!r}")
        return 2
    except Exception as e:
        log(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
