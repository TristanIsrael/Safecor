"""Starts the per-DomU vchan+SFTP channels on sys-usb for direct USB mount.

Queries the topology via MQTT to find the domains with direct_mount enabled,
sandboxes sftp-server with bubblewrap (one sandbox per session, /media/usb
served as the SFTP root, the server running as the dedicated svc-sys-usb-sftp
account with no capabilities), then starts, for each of those domains:
- a socat bridge from a UNIX socket to the sandboxed sftp-server,
- a vchan-socket-proxy server bridging the SFTP vchan channel to that socket.

Runs detached (started by the safecor-vchan-sftp service) and retries the
topology query until MQTT is available, so that the boot is never blocked.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import pwd
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

sys.path.insert(0, "/usr/lib/safecor")

from safecor import Api, MqttFactory, Topics

QUERY_RETRIES = 15
QUERY_TIMEOUT = 10  # seconds, per MQTT query attempt
RETRY_INTERVAL = 5  # seconds between query attempts
DOMAIN_WAIT_TIMEOUT = 60  # seconds to wait for a domain's domid

# /media/usb is bound at the same path in the sandbox and made the working
# directory, so a disk mounted at /media/usb/<label> on sys-usb appears at
# the same path in the client's /media/usb sshfs mount.
SFTP_ROOT = "/media/usb"
SFTP_SERVER = "/usr/lib/ssh/sftp-server"
MUSL_LOADER = "/lib/ld-musl-x86_64.so.1"
SANDBOX_PASSWD = "/usr/lib/safecor/etc/sftp-sandbox-passwd"

# The account the sandboxed sftp-server runs as (created by the package's
# post-install script). The USB disks are owned by this account (mdev mount
# options), so the server needs no capabilities at all.
SFTP_USER = "svc-sys-usb-sftp"


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


def sftp_credentials() -> tuple[int, int]:
    """The (uid, gid) of the SFTP service account.

    The sandboxed sftp-server runs as this account (see bwrap_args). The
    account is created by the package's post-install script.

    Raises:
        KeyError: if the account does not exist.
    """
    pw = pwd.getpwnam(SFTP_USER)
    return pw.pw_uid, pw.pw_gid


def parse_ldd_output(output: str) -> list[str]:
    """The shared library paths from an ldd output (musl/busybox format).

    Dependency lines look like ``libfoo.so.0 => /usr/lib/libfoo.so.0 (...)``;
    the musl loader and libc (bound once, see bwrap_args) are skipped, as
    are unresolved entries.
    """
    libs = []
    for line in output.splitlines():
        parts = line.split()
        if (
            len(parts) >= 3
            and parts[1] == "=>"
            and parts[2].startswith("/")
            and "musl" not in parts[2]
            and parts[2] not in libs
        ):
            libs.append(parts[2])
    return libs


def setpriv_library_paths(setpriv_path: str) -> list[str]:
    """The shared libraries the setpriv binary needs at runtime (via ldd).

    The setpriv package (Alpine main) is linked against version-dependent
    libraries (libcap-ng, and libeconf since util-linux 2.42); all of them
    must be bound into the sandbox, which has no library path.

    Raises:
        subprocess.CalledProcessError: if ldd fails.
    """
    result = subprocess.run(
        ["ldd", setpriv_path], capture_output=True, text=True, check=True
    )
    return parse_ldd_output(result.stdout)


def write_sandbox_passwd(uid: int, gid: int, path: str = SANDBOX_PASSWD) -> str:
    """Write the sandbox's minimal /etc/passwd and return its path.

    sftp-server (OpenSSH 10+) looks up its own uid at startup and exits if
    the account is not in /etc/passwd; the sandbox has no /etc, so a
    single-line file bound over /etc/passwd provides exactly the account the
    server runs as, and nothing else.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        f.write(f"{SFTP_USER}:x:{uid}:{gid}::/:/sbin/nologin\n")
    os.chmod(path, 0o644)
    return path


def bind_dirs(paths: list[str]) -> list[str]:
    """The ancestor directories of the given paths (without the root).

    bwrap creates missing bind-destination parents implicitly with a
    restrictive mode (0700), which breaks the traversal after the setpriv
    switch to the service account; explicit ``--dir`` (0755) keeps the
    sandbox deterministic. Each directory is emitted once, in first-seen
    order, so it always precedes the bind that needs it.
    """
    dirs = []
    for path in paths:
        parts = [p for p in path.split("/") if p]
        for i in range(1, len(parts)):
            d = "/" + "/".join(parts[:i])
            if d not in dirs:
                dirs.append(d)
    return dirs


@dataclass(frozen=True)
class SandboxContext:
    """The host-side inputs of a sftp sandbox (resolved once at start)."""

    setpriv: str
    setpriv_libs: list[str]
    passwd: str


def bwrap_args(mode: str, uid: int, gid: int, ctx: SandboxContext) -> list[str]:
    """The bubblewrap command line sandboxing one sftp-server session.

    The sandbox root is a private tmpfs (nothing it creates reaches the host
    or the client): /media/usb is bound at the same path (read-only for
    ``ro`` channels) and made the working directory, so the served SFTP root
    is the USB mount tree. The sftp-server binary, the setpriv helper, its
    shared libraries, a minimal one-account /etc/passwd and the musl dynamic
    linker are bound in read-only, a fresh /dev is mounted, and the
    pid/ipc/uts/net namespaces are unshared.

    The command runs setpriv as root to drop to the SFTP service account
    (``uid``:``gid``) before exec'ing sftp-server, which then runs with no
    capabilities at all: the USB disks are owned by the account, so no DAC
    override is needed, and the kernel clears the capability sets on the
    setuid switch. Only CAP_SETUID, CAP_SETGID and CAP_SETPCAP are kept in
    the bounding set, for the short-lived root setpriv phase.

    Confinement: bwrap pivots twice into the new root and detaches the old
    one, so the host root filesystem is unreachable from the sandbox (unlike
    a plain chroot, which a root process can escape).
    """
    root_flag = "--ro-bind" if mode == "ro" else "--bind"
    binds: list[tuple[str, str]] = [
        (ctx.passwd, "/etc/passwd"),
        (ctx.setpriv, ctx.setpriv),
        (MUSL_LOADER, MUSL_LOADER),
        *[(lib, lib) for lib in ctx.setpriv_libs],
        (SFTP_SERVER, SFTP_SERVER),
    ]
    args: list[str] = ["bwrap", "--tmpfs", "/", "--dir", SFTP_ROOT]
    args += [root_flag, SFTP_ROOT, SFTP_ROOT]
    dirs_done: set[str] = set()
    for source, dest in binds:
        for d in bind_dirs([dest]):
            if d not in dirs_done:
                args += ["--dir", d]
                dirs_done.add(d)
        args += ["--ro-bind", source, dest]
    args += [
        "--cap-drop",
        "ALL",
        "--cap-add",
        "CAP_SETUID",
        "--cap-add",
        "CAP_SETGID",
        "--cap-add",
        "CAP_SETPCAP",
        "--dev",
        "/dev",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
        "--die-with-parent",
        "--chdir",
        SFTP_ROOT,
        "--",
        ctx.setpriv,
        "--reuid",
        str(uid),
        "--regid",
        str(gid),
        "--clear-groups",
        "--no-new-privs",
        SFTP_SERVER,
        *sftp_server_args(mode),
    ]
    return args


def sandbox_context(uid: int, gid: int) -> SandboxContext:
    """Resolve the host-side inputs of the sftp sandboxes.

    - the setpriv helper (its path varies across Alpine releases: /bin or
      /usr/bin),
    - the shared libraries setpriv needs (ldd),
    - the minimal /etc/passwd bound into the sandbox.

    Raises:
        FileNotFoundError: if setpriv is not installed.
        subprocess.CalledProcessError: if ldd fails.
    """
    setpriv = shutil.which("setpriv")
    if setpriv is None:
        raise FileNotFoundError("setpriv not found in PATH")
    libs = setpriv_library_paths(setpriv)
    passwd = write_sandbox_passwd(uid, gid)
    return SandboxContext(setpriv, libs, passwd)


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


def start_channel(
    name: str, domid: str, mode: str, uid: int, gid: int, ctx: SandboxContext
) -> None:
    """Start the socat bridge and the vchan server for one domain.

    Every client connection is answered with a bubblewrap-sandboxed
    sftp-server (see bwrap_args): the sandbox is spawned per session by
    socat, so no assembly is needed at boot.

    The start is idempotent: the existing socat and vchan-socket-proxy
    instances (by pidfile) are stopped and the stale socket removed before
    starting, so a double start of the service converges to one socat and
    one proxy per domain. The children's output (bind failures, sftp
    session errors) is redirected to a per-domain log.

    The socat UNIX listener is started first: the vchan server connects to
    the socket that socat creates. The SFTP vchan channel data is shared in
    the xenstore namespace /local/domain/system/vchan/<domain>/sftp,
    readable by all DomUs.
    """
    vchan_sock = f"/var/run/safecor/vchan-{name}.sock"
    vchan_path = f"/local/domain/system/vchan/{name}/sftp"
    vchan_log = f"/var/log/safecor/vchan-{name}.log"
    sftp_cmd = " ".join(bwrap_args(mode, uid, gid, ctx))

    subprocess.run(
        [
            "start-stop-daemon",
            "--stop",
            "--pidfile",
            f"/var/run/safecor/socat-{name}.pid",
            "--retry",
            "3",
        ],
        check=False,
    )
    subprocess.run(
        [
            "start-stop-daemon",
            "--stop",
            "--pidfile",
            f"/var/run/safecor/vchan-{name}.pid",
            "--retry",
            "3",
        ],
        check=False,
    )
    try:
        os.remove(vchan_sock)
    except FileNotFoundError:
        pass

    subprocess.run(
        [
            "start-stop-daemon",
            "--start",
            "--background",
            "--make-pidfile",
            "--pidfile",
            f"/var/run/safecor/socat-{name}.pid",
            "--stdout",
            vchan_log,
            "--stderr",
            vchan_log,
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
            "--stdout",
            vchan_log,
            "--stderr",
            vchan_log,
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

    # The bind source of the sandbox root must exist at session spawn
    # (mdev creates the per-disk subdirectories).
    os.makedirs(SFTP_ROOT, exist_ok=True)

    # The sandbox drops to this account (see bwrap_args); it is created by
    # the package's post-install script, so a missing account is fatal.
    try:
        sftp_uid, sftp_gid = sftp_credentials()
    except KeyError:
        log(f"error: the SFTP service account {SFTP_USER!r} does not exist")
        sys.exit(1)

    try:
        ctx = sandbox_context(sftp_uid, sftp_gid)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        log(f"error: cannot prepare the sandbox context: {e}")
        sys.exit(1)

    for name, mode in domains:
        domid = wait_for_domid(name)
        if not domid:
            log(f"warning: no domid found for domain {name}, skipping")
            continue
        log(f"starting vchan SFTP channel for {name} (domid {domid}, mode {mode})")
        start_channel(name, domid, mode, sftp_uid, sftp_gid, ctx)

    log("vchan SFTP channels started")


if __name__ == "__main__":
    main()
