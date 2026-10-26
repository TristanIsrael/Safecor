"""Command-line entry point: ``safecor-emulator``.

Starts the emulated Safecor core (broker + mock Dom0 + mock sys-usb) and keeps
it running so that a Safecor-based product can be launched in another terminal
against it. Use ``--profile`` / ``--disk`` / ``--storage`` / ``--destination``
to shape the emulated system.

Example::

    safecor-emulator --disk usb0=/path/to/files

Then, in another terminal, run your product (e.g. the demo2 app). Press Ctrl+C
here to stop the emulator.
"""

import argparse
import os
import signal
import sys
import tempfile
import time

from safecor_emulator import Emulator, load_profile


def _terminate_on_signal(signum, frame):  # noqa: ARG001
    """Turn SIGTERM into a KeyboardInterrupt so shutdown is clean."""
    raise KeyboardInterrupt


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="safecor-emulator",
        description="Run the emulated Safecor core (broker + mock Dom0 + "
                    "mock sys-usb) without Xen or real hardware.")
    parser.add_argument("--profile",
                        help="path to a system profile JSON file "
                             "(see system_profile.default.json)")
    parser.add_argument("--disk", action="append", default=[], metavar="NAME=PATH",
                        help="source disk to expose (repeatable); NAME is the "
                             "disk id, PATH its root directory")
    parser.add_argument("--storage",
                        help="directory that emulates the repository")
    parser.add_argument("--destination",
                        help="directory that emulates the target disk")
    parser.add_argument("--port", type=int, default=1883,
                        help="broker TCP port (default 1883)")
    parser.add_argument("--host", default="localhost",
                        help="broker host (default localhost)")
    parser.add_argument("--no-reuse", action="store_true",
                        help="start a dedicated broker instead of reusing one "
                             "already listening on the port")
    return parser


def _parse_disks(items):
    disks = {}
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(
                f"--disk expects NAME=PATH, got {item!r}")
        name, path = item.split("=", 1)
        if not name or not path:
            raise argparse.ArgumentTypeError(
                f"--disk expects NAME=PATH, got {item!r}")
        disks[name] = path
    return disks


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    profile = load_profile(args.profile)
    source_disks = _parse_disks(args.disk)

    # Default working locations under a temp dir when not given
    workdir = os.path.join(tempfile.gettempdir(), "safecor_emulator")
    os.makedirs(workdir, exist_ok=True)
    storage = args.storage or os.path.join(workdir, "repository")
    destination = args.destination or os.path.join(workdir, "target")

    em = Emulator(
        profile=profile,
        source_disks=source_disks,
        storage_path=storage,
        destination_disk_path=destination,
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
    print(f"  profile     : uuid={profile.uuid} cpu_count={profile.cpu_count} "
          f"screen={profile.screen_width}x{profile.screen_height}")
    print(f"  repository  : {storage}")
    print(f"  target disk : {destination}")
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
