"""Command-line entry point: ``safecor-emulator``

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import argparse
import os
import signal
import sys
import tempfile
import time

from safecor_emulator import Emulator, load_profile


def _terminate_on_signal(signum, frame):
    """Turn SIGTERM into a KeyboardInterrupt so shutdown is clean."""
    raise KeyboardInterrupt


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="safecor-emulator",
        description="Run the emulated Safecor core (broker + mock Dom0 + "
        "mock sys-usb) without Xen or real hardware.",
    )
    parser.add_argument(
        "--profile",
        help="path to a system profile JSON file (see system_profile.default.json)",
    )
    parser.add_argument(
        "--disk",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="source disk to expose (repeatable); NAME is the "
        "disk id, PATH its root directory",
    )
    parser.add_argument("--storage", help="directory that emulates the repository")
    parser.add_argument(
        "--port", type=int, default=1883, help="broker TCP port (default 1883)"
    )
    parser.add_argument(
        "--host", default="localhost", help="broker host (default localhost)"
    )
    parser.add_argument(
        "--no-reuse",
        action="store_true",
        help="start a dedicated broker instead of reusing one "
        "already listening on the port",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="start the graphical operator console (QML window) "
        "instead of the headless core; optionally accepts --topology "
        "(a topology can also be loaded later from the Setup panel) "
        "and needs the optional ``gui`` extra (PySide6)",
    )
    parser.add_argument(
        "--topology",
        help="path to a product topology.json (optional with --gui; can "
        "also be loaded later from the Setup panel); shapes the emulated "
        "environment (product, screen, languages, business domains, "
        "hardware configurations)",
    )
    return parser


def _parse_disks(items):
    disks = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"--disk expects NAME=PATH, got {item!r}")
        name, path = item.split("=", 1)
        if not name or not path:
            raise argparse.ArgumentTypeError(f"--disk expects NAME=PATH, got {item!r}")
        disks[name] = path
    return disks


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        # --topology is optional: without it the console starts on the standard
        # environment and the operator can load one from the Setup panel.
        # Imported lazily so the headless path does not require PySide6.
        try:
            from safecor_emulator.gui import run_gui
        except ImportError as exc:
            parser.error(
                f"--gui needs PySide6 (the optional 'gui' extra); install it with "
                f"`pip install 'safecor-emulator[gui]'` ({exc})"
            )
        return run_gui(
            topology_path=args.topology,
            broker_port=args.port,
            host=args.host,
            reuse_broker=not args.no_reuse,
        )

    profile = load_profile(args.profile)
    source_disks = _parse_disks(args.disk)

    # Default working locations under a temp dir when not given
    workdir = os.path.join(tempfile.gettempdir(), "safecor_emulator")
    os.makedirs(workdir, exist_ok=True)
    storage = args.storage or os.path.join(workdir, "repository")

    em = Emulator(
        profile=profile,
        source_disks=source_disks,
        storage_path=storage,
        broker_port=args.port,
        host=args.host,
        reuse_broker=not args.no_reuse,
    )

    try:
        em.start()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: failed to start the emulator: {e}", file=sys.stderr)
        return 1

    broker_state = "started" if em._own_broker else "reused"
    print("Safecor emulator is running.")
    print(f"  broker      : {args.host}:{args.port} ({broker_state})")
    print(
        f"  profile     : uuid={profile.uuid} cpu_count={profile.cpu_count} "
        f"screen={profile.screen_width}x{profile.screen_height}"
    )
    print(f"  repository  : {storage}")
    for name, path in source_disks.items():
        print(f"  disk {name}: {path}")
    print("Press Ctrl+C to stop.")

    signal.signal(signal.SIGTERM, _terminate_on_signal)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping the emulator...")
    finally:
        em.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
