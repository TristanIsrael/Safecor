"""USB passthrough controller (Dom0 side)

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import base64
import json
import os
import pwd
import shutil
import subprocess
import threading
import time
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

from . import (
    ComponentState,
    Constants,
    FileHelper,
    MountMode,
    MqttClient,
    MqttHelper,
    ResponseFactory,
    System,
    Topics,
)

try:
    from . import DiskMonitor
except ImportError:
    print("SysUsbController cannot use DiskMonitor")
from . import DiskState, Logger, NotificationFactory

try:
    from . import InputsDaemon

    NO_INPUTS_MONITORING = False
except ImportError:
    NO_INPUTS_MONITORING = True
    print(
        "Importing ControleurVmSysUsb without inputs monitoring nor benchmarking capacity"
    )


####
# SFTP channels of the direct USB mount
#
# The SFTP side of the direct mount feature: for every domain with
# ``direct_mount`` in the topology, one socat bridge (UNIX socket, one
# sandboxed sftp-server per session) and one vchan-socket-proxy server (the
# "sftp" PV channel) are started on sys-usb.
#
# The channels are (un)started by the root channels helper
# (safecor-dm-channels.py, run through doas by the controller): the
# per-session sandbox (bwrap -> setpriv -> sftp-server) needs a root parent
# to drop to the SFTP service account. See the component documentation
# (docs/architecture/components/direct-usb-mount.md).
#
# A local persistent log at /var/log/safecor/direct-mount.log (created by the
# controller initd) records all channel-lifecycle events, complementing the
# ephemeral MQTT-based Logger.

# /media/usb is bound at the same path in the sandbox and made the working
# directory, so a disk mounted at /media/usb/<label> on sys-usb appears at
# the same path in the client's /media/usb sshfs mount.
SFTP_ROOT = "/media/usb"
SFTP_SERVER = "/usr/lib/ssh/sftp-server"
MUSL_LOADER = "/lib/ld-musl-x86_64.so.1"

# The account the sandboxed sftp-server runs as (created by the package's
# post-install script). The USB disks are owned by this account (mdev mount
# options), so the server needs no capabilities at all.
SFTP_USER = "svc-sys-usb-sftp"

# Runtime files of the channels (created by the controller initd at every
# boot, owned by the controller user): the UNIX socket, the pidfiles, the
# per-domain log and the sandbox passwd of every channel.
SFTP_RUNTIME_DIR = "/var/run/safecor/direct-mount"
SANDBOX_PASSWD = f"{SFTP_RUNTIME_DIR}/sftp-sandbox-passwd"

# The root helper that starts and stops the channels (see the doas
# configuration of the controller user).
DM_CHANNELS_HELPER = "/usr/lib/safecor/bin/safecor-dm-channels.py"

# One-shot my_config query timeout (seconds), a bounded wait running in the
# channel thread (NFR-1 constrains the MQTT callbacks only).
MY_CONFIG_QUERY_TIMEOUT = 10


def parse_direct_mount_domains(response: dict) -> list[tuple[str, MountMode]]:
    """Extract the (name, mode) pairs of the direct_mount domains.

    The mode is a MountMode (RO or RW, default RW). A falsy direct_mount
    value (False, None, an empty dict) means the domain is not enabled, as
    in the DirectMountManager reference. A non-dict truthy value (e.g. a
    bare true) or an invalid mode defaults to RW.
    """
    pairs = []
    for d in response.get("domains", []):
        dm = d.get("direct_mount")
        if not dm:
            continue
        raw_mode = dm.get("mode") if isinstance(dm, dict) else None
        if raw_mode == MountMode.RO.value:
            mode = MountMode.RO
        elif raw_mode == MountMode.RW.value:
            mode = MountMode.RW
        else:
            Logger().warn(
                f"Invalid direct_mount mode {raw_mode!r} for domain "
                f"{d.get('name')!r}, using 'rw'"
            )
            mode = MountMode.RW
        pairs.append((d["name"], mode))
    return pairs


def sftp_server_args(mode: MountMode) -> list[str]:
    """The sftp-server command-line arguments for a mount mode.

    -u 077: no group or other permissions on the files sftp-server creates.
    -R: read-only mode (open for write and every state-changing request are
        denied), for RO domains.
    """
    args = ["-u", "077"]
    if mode == MountMode.RO:
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


def bwrap_args(mode: MountMode, uid: int, gid: int, ctx: SandboxContext) -> list[str]:
    """The bubblewrap command line sandboxing one sftp-server session.

    The sandbox root is a private tmpfs (nothing it creates reaches the host
    or the client): /media/usb is bound at the same path (read-only for
    ``RO`` channels) and made the working directory, so the served SFTP root
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
    root_flag = "--ro-bind" if mode == MountMode.RO else "--bind"
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


def stop_sftp_channel(name: str) -> None:
    """Stops the socat bridge and the vchan server of one domain (as root).

    Best-effort: a missing pidfile or socket is not an error.
    """
    subprocess.run(
        [
            "start-stop-daemon",
            "--stop",
            "--pidfile",
            f"{SFTP_RUNTIME_DIR}/socat-{name}.pid",
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
            f"{SFTP_RUNTIME_DIR}/vchan-{name}.pid",
            "--retry",
            "3",
        ],
        check=False,
    )
    try:
        os.remove(f"{SFTP_RUNTIME_DIR}/vchan-{name}.sock")
    except FileNotFoundError:
        pass


def start_sftp_channel(
    name: str,
    domid: int,
    mode: MountMode,
    uid: int,
    gid: int,
    ctx: SandboxContext,
) -> None:
    """Starts the socat bridge and the vchan server for one domain (as root).

    Every client connection is answered with a bubblewrap-sandboxed
    sftp-server (see bwrap_args): the sandbox is spawned per session by
    socat, so no assembly is needed at boot.

    The start is idempotent: the existing socat and vchan-socket-proxy
    instances (by pidfile) are stopped and the stale socket removed before
    starting, so a double start converges to one socat and one proxy per
    domain. The children's output (bind failures, sftp session errors) is
    redirected to a per-domain log.

    The socat UNIX listener is started first: the vchan server connects to
    the socket that socat creates. The SFTP vchan channel data is shared in
    the xenstore namespace /local/domain/system/vchan/<domain>/sftp,
    readable by all DomUs.

    Raises:
        subprocess.CalledProcessError: if a start-stop-daemon call fails.
    """
    vchan_sock = f"{SFTP_RUNTIME_DIR}/vchan-{name}.sock"
    vchan_path = f"/local/domain/system/vchan/{name}/sftp"
    vchan_log = f"{SFTP_RUNTIME_DIR}/vchan-{name}.log"
    sftp_cmd = " ".join(bwrap_args(mode, uid, gid, ctx))

    stop_sftp_channel(name)

    subprocess.run(
        [
            "start-stop-daemon",
            "--start",
            "--background",
            "--make-pidfile",
            "--pidfile",
            f"{SFTP_RUNTIME_DIR}/socat-{name}.pid",
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
            f"{SFTP_RUNTIME_DIR}/vchan-{name}.pid",
            "--stdout",
            vchan_log,
            "--stderr",
            vchan_log,
            "--exec",
            "/usr/bin/vchan-socket-proxy",
            "--",
            "-m",
            "server",
            str(domid),
            vchan_path,
            vchan_sock,
        ],
        check=True,
    )


class SysUsbController:
    """This class handles messages exchanged between sys-usb and the Dom0 or the other Domains

    The controller hosts the components published on
    :attr:`Topics.DISCOVER_COMPONENTS` (see :func:`__publish_component_states`):
    the disk controller, the input controller and the direct mount component
    (``safecor_direct_mount``), the SFTP channels of the direct USB mount.
    The state of the direct mount component is the single synchronization
    point of the feature (NFR-3): the business DomUs mount /media/usb when
    they are notified of its READY state.
    """

    __nb_mqtt_conn = 0
    __can_run = True
    __messages_queue = Queue()
    __read_files_queue = Queue()
    __copy_files_queue = Queue()
    __high_priority_messages = [
        Topics.LIST_DISKS,
        Topics.LIST_FILES,
        Topics.DISCOVER_COMPONENTS,
        Topics.PING,
        Topics.SYS_USB_CLEAR_QUEUES,
        Topics.MOUNT_FILE,
    ]

    def __init__(self, mqtt_client: MqttClient):
        self.mqtt_client = mqtt_client
        self.__disk_monitor = None
        self.__thread_read_files = threading.Thread(
            target=self.__read_files_worker, name="read_file_worker"
        )
        self.__thread_copy_files = threading.Thread(
            target=self.__copy_files_worker, name="copy_file_worker"
        )
        self.__thread_messages = threading.Thread(
            target=self.__message_worker, name="message_worker"
        )

        # State of the components hosted by this controller (published on
        # Topics.DISCOVER_COMPONENTS): the disk/input controllers share
        # __controller_state, the direct mount component carries the state
        # of the SFTP channels.
        self.__controller_state = ComponentState.READY
        self.__direct_mount_state = ComponentState.STARTING
        self.__sftp_channels: list[str] = []
        self.__channels_thread_started = False

        # One-shot my_config query (see __query_direct_mount_domains)
        self.__my_config_result = None
        self.__my_config_event = threading.Event()

    def __del__(self):
        self.__can_run = False

    def start(self):
        self.mqtt_client.on_connected = self.__on_mqtt_connected
        self.mqtt_client.on_message = self.__on_mqtt_message

        self.mqtt_client.start()

        self.__can_run = True

    def stop(self):
        self.__can_run = False
        InputsDaemon().stop()
        self.__shutdown_direct_mount()

    def __on_mqtt_connected(self):
        Logger().setup("USB controller", self.mqtt_client)
        Logger().debug("Starting Safecor disk controller")

        self.mqtt_client.subscribe(f"{Topics.LIST_DISKS}/request")
        self.mqtt_client.subscribe(f"{Topics.LIST_FILES}/request")
        self.mqtt_client.subscribe(f"{Topics.COPY_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.READ_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.DELETE_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.MOUNT_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.UNMOUNT}/request")
        # self.mqtt_client.subscribe(f"{Topics.BENCHMARK}/request")
        self.mqtt_client.subscribe(f"{Topics.FILE_FINGERPRINT}/request")
        self.mqtt_client.subscribe(f"{Topics.CREATE_FILE}/request")
        self.mqtt_client.subscribe(f"{Topics.DISCOVER_COMPONENTS}/request")
        self.mqtt_client.subscribe(f"{Topics.PING}/request")
        self.mqtt_client.subscribe(f"{Topics.SYS_USB_CLEAR_QUEUES}/request")
        self.mqtt_client.subscribe(f"{Topics.RESTART_DOMAIN}/request")
        # Response of the one-shot my_config query (see
        # __query_direct_mount_domains): intercepted in __on_mqtt_message
        self.mqtt_client.subscribe(f"{Topics.MY_CONFIG}/response")

        # Démarrage de la surveillance des entrées
        if not NO_INPUTS_MONITORING:
            InputsDaemon().start(self.mqtt_client)

        # ControleurBenchmark().setup(self.mqtt_client)
        # Start threads
        self.__thread_read_files.start()
        self.__thread_copy_files.start()
        self.__thread_messages.start()

        self.__disk_monitor = DiskMonitor(Constants.USB_MOUNT_POINT, self.mqtt_client)
        threading.Thread(target=self.__disk_monitor.start).start()

        self.__handle_discover_components()

        # Start the SFTP channels of the direct_mount domains in a
        # dedicated thread: the one-shot my_config query is a bounded wait,
        # allowed outside of the MQTT callbacks (NFR-1).
        if not self.__channels_thread_started:
            self.__channels_thread_started = True
            threading.Thread(
                target=self.__start_direct_mount_channels,
                name="direct_mount_channels",
                daemon=True,
            ).start()

    def __on_mqtt_message(self, topic: str, payload: dict):
        # Logger().debug("Message received : topic={}, payload={}".format(topic, payload))

        # The my_config response is consumed by the direct mount channel
        # thread (one-shot query): route it here, before the queue, so the
        # callback stays non-blocking (NFR-1).
        if topic == f"{Topics.MY_CONFIG}/response":
            if self.__accept_my_config_response(payload):
                self.__my_config_result = payload
                self.__my_config_event.set()
            return

        base_topic, _ = topic.rsplit("/", 1)

        # Some messages have a high priority, we don't put them into the queue
        # These tasks should only be small tasks, otherwise they go in the queue
        if base_topic in self.__high_priority_messages:
            threading.Thread(target=self.__handle_message(base_topic, payload)).start()
            return

        self.__messages_queue.put((base_topic, payload))

    def __message_worker(self):
        # Logger().debug("Handle message {}".format(topic))

        while self.__can_run:
            if not self.__messages_queue.empty():
                message = self.__messages_queue.get()  # We get a tuple
                topic = message[0]
                payload = message[1]

                self.__handle_message(topic, payload)

            time.sleep(0.1)

    ####
    # Traitement des commandes
    #
    def __handle_message(self, topic: str, payload: dict):
        if topic == Topics.LIST_DISKS:
            self.__handle_list_disks(topic)
        elif topic == Topics.LIST_FILES:
            self.__handle_list_files(topic, payload)
        elif topic == Topics.COPY_FILE:
            self.__handle_copy_file(topic, payload)
        elif topic == Topics.READ_FILE:
            self.__handle_read_file(topic, payload)
        # elif topic == Topics.DELETE_FILE:
        #    self.__handle_remove_file(topic, payload)
        elif topic == Topics.BENCHMARK:
            self.__handle_benchmark(topic, payload)
        elif topic == Topics.FILE_FINGERPRINT:
            self.__handle_file_fingerprint(topic, payload)
        elif topic == Topics.CREATE_FILE:
            self.__handle_create_file(topic, payload)
        elif topic == Topics.DISCOVER_COMPONENTS:
            self.__handle_discover_components()
        elif topic == Topics.DELETE_FILE:
            self.__handle_delete_file(payload)
        elif topic == Topics.PING:
            self.__handle_ping(payload)
        elif topic == Topics.SYS_USB_CLEAR_QUEUES:
            self.__handle_clear_queue()
        elif topic == Topics.MOUNT_FILE:
            self.__handle_mount_file(payload)
        elif topic == Topics.UNMOUNT:
            self.__handle_unmount(payload)
        elif topic == Topics.RESTART_DOMAIN:
            self.__handle_restart(payload)

    def __handle_list_disks(self, topic: str) -> None:
        Logger().debug("Disks list requested")

        # Get list of mount points
        disks = FileHelper.get_disks_list()
        # print(disks)

        # Génère la réponse
        response = ResponseFactory.create_response_disks_list(disks)
        self.mqtt_client.publish(f"{topic}/response", response)

    def __handle_list_files(self, topic: str, payload: dict) -> None:
        # Verify the arguments
        if not MqttHelper.check_payload(payload, ["disk", "recursive", "from_dir"]):
            Logger().error(f"Missing arguments for {topic}")
            return

        disk = payload.get("disk", "")
        recursive = payload.get("recursive", False)
        from_dir = payload.get("from_dir", "")
        name_filter = payload.get("name_filter", None)

        if disk == Constants.STR_REPOSITORY:
            return

        # Get the files list
        files = FileHelper.get_files_list(disk, recursive, from_dir, name_filter)

        # Generate the response
        response = ResponseFactory.create_response_list_files(disk, files)
        self.mqtt_client.publish(f"{topic}/response", response)

    def __handle_read_file(self, topic: str, payload: dict):
        # La copie de fichier consiste à lire le fichier depuis le support externe
        # et à le placer dans le dépôt du système.
        # Une empreinte est calculée lors de la copie et transmise dans la réponse
        # Cette fonction est réentrante, le système gère le nombre de copies parallèles
        # en fonction des ressources disponibles.
        # Les arguments de la commande sont :
        # - nom_fichier au format disk:filename
        # - nom_disque_destination
        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            Logger().error(f"Missing argument(s) for the command {topic}")
            return

        source_disk = payload.get("disk", "")
        filepath = payload.get("filepath", "")
        repository_path: str = Constants.DOMU_REPOSITORY_PATH

        # source_location = f"{Constants.USB_MOUNT_POINT}/{source_disk}"
        mount_point = FileHelper.get_mount_point(source_disk)
        # source_location = f"{Constants.USB_MOUNT_POINT}/{source_disk}"
        source_fingerprint = FileHelper.calculate_fingerprint(
            f"{mount_point}/{filepath}"
        )

        dest_parent_path = Path(f"{repository_path}/{filepath}").parent
        if not dest_parent_path.exists():
            # print(f"Create directory {dest_parent_path} in {mount_point}")
            os.makedirs(dest_parent_path.as_posix(), exist_ok=True)

        self.__read_files_queue.put(
            {
                "source_location": mount_point,
                "source_disk": source_disk,
                "filepath": filepath,
                "repository_path": repository_path,
                "source_fingerprint": source_fingerprint,
            }
        )
        # self.task_runner.run_task(self.__do_read_file, args=(source_location, source_disk, filepath, repository_path, source_fingerprint,))

    # def __handle_remove_file(self, topic:str, payload: dict):
    # Logger().error("The command remove file is not implemented")
    # Not implemented on sys-usb
    #    pass

    def __handle_copy_file(self, topic: str, payload: dict):
        if not MqttHelper.check_payload(payload, ["disk", "filepath", "destination"]):
            Logger().error(f"Missing arguments for the request {topic}")
            return

        source_disk = payload.get("disk", "")
        filepath = payload.get("filepath", "")
        target_disk = payload.get("destination", "")

        source_location = f"{Constants.USB_MOUNT_POINT}/{source_disk}"
        destination_location = f"{Constants.USB_MOUNT_POINT}/{target_disk}"

        try:
            self.__copy_files_queue.put(
                {
                    "source_location": source_location,
                    "source_disk": source_disk,
                    "filepath": filepath,
                    "target_disk": target_disk,
                    "destination_location": destination_location,
                }
            )
            # self.task_runner.run_task(self.__do_copy_file, args=(source_location, filepath, target_disk, destination_location,))
        except Exception:
            Logger().error(
                f"An error occured while copying the file {filepath} on {target_disk}"
            )

        # FichierHelper.copy_file(disk, filepath, destination_folder)

    def __handle_benchmark(self, topic: str, payload: dict):
        module = payload.get("module")

        if module is None:
            Logger().error(f"Argument missing: module. Topic is {topic}")
            return

    def __handle_file_fingerprint(self, topic: str, payload: dict):
        disk = payload.get("disk")
        filepath = payload.get("filepath")

        if disk is not None and disk == Constants.STR_REPOSITORY:
            # Ignored
            return

        if disk is None:
            Logger().error(f"fArgument missing: disk. Topic is {topic}")
            return

        if filepath is None:
            Logger().error(f"Argument missing: filepath. Topic is {topic}")
            return

        Logger().debug(
            f"Calculate fingerprint of the file {filepath} on the disk {disk}"
        )

        mount_point = Constants.USB_MOUNT_POINT
        fingerprint = FileHelper.calculate_fingerprint(
            f"{mount_point}/{disk}/{filepath}"
        )

        Logger().info(
            f"The fingerprint of the file {disk} on the disk {filepath} is {fingerprint}"
        )

        response = ResponseFactory.create_response_file_fingerprint(
            filepath, disk, fingerprint
        )
        self.mqtt_client.publish(f"{topic}/response", response)

    def __handle_create_file(self, topic: str, payload: dict):
        disk = payload.get("disk", "")
        filepath = payload.get("filepath", "")
        base64_data = payload.get("data", "")

        if not MqttHelper.check_payload(payload, ["disk", "filepath", "data"]):
            Logger().error("Missing argument in the create_file command")
            return

        if disk == Constants.STR_REPOSITORY:
            # Ignored
            return

        decoded = base64.b64decode(base64_data)

        # Check if data were compressed, and uncompress if needed
        compressed = payload.get("compressed", False)
        if compressed:
            data = zlib.decompress(decoded)
        else:
            data = decoded

        mount_point = Constants.USB_MOUNT_POINT
        complete_filepath = f"{mount_point}/{disk}/{filepath}"

        Logger().debug(
            f"Create a file {filepath} of size {len(data)} octets on disk {disk}"
        )

        try:
            with open(complete_filepath, "wb") as f:
                f.write(data)
            f.close()
        except Exception as e:
            Logger().error(
                f"An error occured while writing to file {complete_filepath}"
            )
            Logger().error(str(e))

            response = ResponseFactory.create_response_create_file(
                filepath, disk, "", False
            )
            self.mqtt_client.publish(f"{topic}/response", response)
            return

        # On envoie la notification de succès
        fingerprint = FileHelper.calculate_fingerprint(complete_filepath)
        response = ResponseFactory.create_response_create_file(
            complete_filepath, disk, fingerprint, True
        )
        self.mqtt_client.publish(f"{topic}/response", response)

    def __handle_discover_components(self) -> None:
        # Reports the current state of the direct mount component (not a
        # hardcoded READY), so the diagnostics show the channel progress.
        self.__publish_component_states()

    def __publish_component_states(self) -> None:
        """Publishes the state of the components hosted by this controller.

        The direct mount component (``safecor_direct_mount``) carries the
        current state of the SFTP channels: STARTING until the channel
        start pass completed for every direct_mount domain (channels started
        and verified alive), READY only when all channels are alive (otherwise
        the component stays STARTING with an error naming the failed domains
        — recovery by restarting the controller service), OFF on shutdown.
        Channel-lifecycle events are also recorded to /var/log/safecor/direct-mount.log.
        It is the single synchronization point of the direct USB mount
        (NFR-3): the business DomUs react to its notification (READY => mount,
        OFF => unmount) instead of polling.
        """
        comp1 = ResponseFactory.create_entry_component_state(
            Constants.SAFECOR_DISK_CONTROLLER,
            "System disk controller",
            "sys-usb",
            self.__controller_state,
            "core",
        )
        comp2 = ResponseFactory.create_entry_component_state(
            Constants.SAFECOR_INPUT_CONTROLLER,
            "Input controller",
            "sys-usb",
            self.__controller_state,
            "core",
        )
        comp3 = ResponseFactory.create_entry_component_state(
            Constants.SAFECOR_DIRECT_MOUNT,
            "Direct USB mount",
            "sys-usb",
            self.__direct_mount_state,
            "core",
        )

        payload = ResponseFactory.create_response_component_state([comp1, comp2, comp3])

        try:
            self.mqtt_client.publish(f"{Topics.DISCOVER_COMPONENTS}/response", payload)
        except Exception as e:
            Logger().error(f"Could not publish the component states: {e}")

    def __handle_delete_file(self, payload):
        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            Logger().error(
                f"The command {Topics.DELETE_FILE} misses argument(s)", "sys-usb"
            )
            return

        disk = payload["disk"]

        if disk == Constants.STR_REPOSITORY:
            # This file is the repository so we ignore it
            return

        filepath = payload["filepath"]
        # mount_point = Constants.USB_MOUNT_POINT
        mount_point = FileHelper.get_mount_point(disk)
        storage_filepath = f"{mount_point}/{filepath}"

        if not FileHelper().remove_file(storage_filepath):
            Logger().error(f"Removal of file {filepath} from the disk {disk} failed")
        else:
            notif = NotificationFactory.create_notification_deleted_file(disk, filepath)
            self.mqtt_client.publish(Topics.DELETED_FILE, notif)
            Logger().info(f"Removed file {filepath} from the disk {disk}")

    def __handle_ping(self, payload):
        ping_id = payload.get("id", "")
        data = payload.get("data", "")
        sent_at = payload.get("sent_at", "")

        payload = ResponseFactory.create_response_ping(
            ping_id, "sys-usb", data, sent_at
        )

        self.mqtt_client.publish(f"{Topics.PING}/response", payload)

    def __handle_restart(self, payload):
        if not MqttHelper.check_payload(payload, ["domain_name"]):
            Logger().error(
                f"The command {Topics.RESTART_DOMAIN} misses argument(s)", "sys-usb"
            )
            return

        domain_name = payload.get("domain_name", "")

        if domain_name == "sys-usb":
            # Publish the components OFF and stop the SFTP channels before
            # the reboot, so the direct mount managers unmount
            self.__shutdown_direct_mount()

            cmd = ["/usr/bin/doas", "/sbin/reboot"]
            subprocess.run(cmd, check=False)

    ####
    # Direct USB mount (SFTP channels)
    #
    def __set_direct_mount_state(self, state: ComponentState) -> None:
        """Updates the state of the direct mount component and publishes it."""
        self.__direct_mount_state = state
        self.__log_channel_event(f"Direct USB mount component state -> {state.value}")
        self.__publish_component_states()

    def __accept_my_config_response(self, payload: dict) -> bool:
        """Returns True if a my_config response is the one we asked for.

        The my_config response topic is shared by all the requesters of the
        bus: a response filtered for another domain never lists sys-usb
        itself, while the full topology (which the controller requests
        without a domain filter) always does.
        """
        return any(d.get("name") == "sys-usb" for d in payload.get("domains", []))

    def __query_direct_mount_domains(self) -> list[tuple[str, MountMode]] | None:
        """One-shot my_config query: the direct_mount domains of the topology.

        Publishes the request on the controller's own client and waits
        (bounded by MY_CONFIG_QUERY_TIMEOUT) for the response, which is
        routed here by __on_mqtt_message. The bounded wait runs in the
        channel thread, so it does not block the MQTT callbacks (NFR-1).

        Returns:
            The (name, MountMode) pairs of the enabled domains, or None if
            no definitive answer arrived in time (NFR-3: no retry).
        """
        self.__my_config_result = None
        self.__my_config_event.clear()
        self.mqtt_client.publish(f"{Topics.MY_CONFIG}/request", {})
        if not self.__my_config_event.wait(timeout=MY_CONFIG_QUERY_TIMEOUT):
            return None
        if self.__my_config_result is None:
            return None
        return parse_direct_mount_domains(self.__my_config_result)

    def __log_channel_event(self, message: str, level: str = "info") -> None:
        """Emits a channel-lifecycle event through Logger and the local log file.

        Publishes through the existing Logger (MQTT bus, ephemeral) at the
        given level (default info) and appends a timestamped line to
        /var/log/safecor/direct-mount.log (persistent, best-effort). A failed
        local write never raises -- a write error is silently ignored so it
        never breaks the controller.
        """
        if level == "error":
            Logger().error(message)
        else:
            Logger().info(message)
        try:
            Path("/var/log/safecor").mkdir(parents=True, exist_ok=True)
            with open("/var/log/safecor/direct-mount.log", "a") as f:
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                f.write(f"{ts} {message}\n")
        except OSError:
            pass  # best-effort: never break the controller

    def __wait_for_domid(
        self, name: str, timeout: float = 60.0, interval: float = 1.0
    ) -> int | None:
        """Polls for a domain's domid until it is found or timeout elapses.

        Runs in the dedicated channel thread (blocking is allowed).
        Returns the domid when found, or None on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            domid = System().get_domain_domid(name)
            if domid is not None:
                return domid
            time.sleep(interval)
        return None

    def __start_direct_mount_channels(self) -> None:
        """Starts the SFTP channels of the direct_mount domains (dedicated thread).

        The my_config query is one-shot (NFR-3): if it fails the component
        stays STARTING (visible in the diagnostics) instead of retrying.
        The domid of each domain is fetched with a bounded wait (1 s interval,
        60 s per domain timeout): Dom0 registers the domids at domain creation,
        which may happen after the channel thread begins on slow boots.
        If a domid is not found after the timeout, the channel is skipped with
        an ERROR event naming the domain, and the component stays STARTING.
        After all channels are started, a liveness verification (pidfiles +
        socket, ~1 s settle) runs; if it fails the channel is marked failed.
        READY is published only when every channel has started and is alive;
        otherwise the component stays STARTING with an ERROR event summarizing
        the failed domains. Each channel-lifecycle event is logged both to the
        MQTT Logger and to /var/log/safecor/direct-mount.log (best-effort).
        """
        pairs = self.__query_direct_mount_domains()
        if pairs is None:
            self.__log_channel_event(
                "The direct_mount domains could not be determined "
                "(my_config timeout), the SFTP channels are not started"
            )
            return

        if not pairs:
            self.__log_channel_event("No domain with direct_mount in the topology")
            self.__set_direct_mount_state(ComponentState.READY)
            return

        failures: list[str] = []

        for name, mode in pairs:
            domid = self.__wait_for_domid(name)
            if domid is None:
                self.__log_channel_event(
                    f"No domid found for domain {name} after timeout, "
                    f"its SFTP channel is skipped",
                    level="error",
                )
                failures.append(name)
                continue
            self.__log_channel_event(
                f"Starting the SFTP channel for {name} (domid {domid}, "
                f"mode {mode.value})"
            )
            if not self.__run_channels_helper(
                {"action": "start", "name": name, "domid": domid, "mode": mode.value}
            ):
                self.__log_channel_event(
                    f"Starting the SFTP channel for {name} failed (helper error)",
                    level="error",
                )
                failures.append(name)
                continue
            # Liveness verification: wait for settle, then check pidfiles + socket.
            time.sleep(1)
            verified = True
            for kind in ("socat", "vchan"):
                pidfile = f"{SFTP_RUNTIME_DIR}/{kind}-{name}.pid"
                try:
                    pid = int(Path(pidfile).read_text().strip())
                except (OSError, ValueError):
                    verified = False
                    break
                if not os.path.exists(f"/proc/{pid}"):
                    verified = False
                    break
            if kind == "vchan" and not os.path.exists(
                f"{SFTP_RUNTIME_DIR}/vchan-{name}.sock"
            ):
                verified = False
            if not verified:
                self.__log_channel_event(
                    f"Starting the SFTP channel for {name} failed "
                    f"(liveness verification)",
                    level="error",
                )
                failures.append(name)
                continue
            self.__sftp_channels.append(name)

        if failures:
            self.__log_channel_event(
                f"SFTP channel start completed with failures: "
                f"{', '.join(failures)} — component stays STARTING",
                level="error",
            )
            # Do NOT set READY; stay STARTING.
        else:
            self.__log_channel_event(
                "All SFTP channels started and verified alive — component READY"
            )
            self.__set_direct_mount_state(ComponentState.READY)

    def __run_channels_helper(self, spec: dict) -> bool:
        """Runs the root channels helper (through doas) with a JSON spec.

        The helper starts or stops the socat bridge and the vchan server of
        one domain (see start_sftp_channel / stop_sftp_channel). It runs as
        root because the per-session sftp sandbox needs a root parent to
        drop to the SFTP service account; the controller user is granted
        this single command in the doas configuration.

        Returns:
            True if the helper exited successfully.
        """
        try:
            result = subprocess.run(
                ["/usr/bin/doas", DM_CHANNELS_HELPER, json.dumps(spec)],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as e:
            Logger().error(f"Could not run the channels helper: {e}")
            return False

        if result.returncode != 0:
            Logger().error(
                f"The channels helper failed (spec {spec}): {result.stderr.strip()}"
            )
            return False
        return True

    def __stop_direct_mount_channels(self) -> None:
        """Stops the SFTP channels (best-effort, through the root helper)."""
        for name in list(self.__sftp_channels):
            self.__run_channels_helper({"action": "stop", "name": name})
        self.__sftp_channels.clear()

    def __shutdown_direct_mount(self) -> None:
        """Publishes the components OFF and stops the SFTP channels (best-effort).

        Logs the transition to the local log file (/var/log/safecor/direct-mount.log).
        """
        self.__controller_state = ComponentState.OFF
        self.__direct_mount_state = ComponentState.OFF
        self.__log_channel_event("Direct USB mount component state -> off (shutdown)")
        self.__publish_component_states()
        self.__stop_direct_mount_channels()

    def __read_files_worker(self):
        while self.__can_run:
            if not self.__read_files_queue.empty():
                next_file = self.__read_files_queue.get()
                source_location = next_file.get("source_location", "")
                source_disk = next_file.get("source_disk", "")
                filepath = next_file.get("filepath", "")
                repository_path = next_file.get("repository_path", "")
                source_fingerprint = next_file.get("source_fingerprint", "")
                self.__do_read_file(
                    source_location,
                    source_disk,
                    filepath,
                    repository_path,
                    source_fingerprint,
                )

            time.sleep(0.1)

    def __copy_files_worker(self):
        while self.__can_run:
            if not self.__copy_files_queue.empty():
                next_file = self.__copy_files_queue.get()
                source_location = next_file.get("source_location", "")
                filepath = next_file.get("filepath", "")
                target_disk = next_file.get("target_disk", "")
                destination_location = next_file.get("destination_location", "")
                self.__do_copy_file(
                    source_location, filepath, target_disk, destination_location
                )

            time.sleep(0.1)

    def __do_read_file(
        self,
        source_location: str,
        source_disk: str,
        filepath: str,
        repository_path: str,
        source_fingerprint: str,
    ):
        # self.__debug_threads()

        dest_fingerprint = FileHelper.copy_file(
            source_location, filepath, repository_path, source_fingerprint
        )
        if dest_fingerprint != "":
            notif = NotificationFactory.create_notification_new_file(
                Constants.STR_REPOSITORY, filepath, source_fingerprint, dest_fingerprint
            )
            self.mqtt_client.publish(Topics.NEW_FILE, notif)
        else:
            notif = NotificationFactory.create_notification_error(
                source_disk, filepath, "The file could not be copied"
            )
            self.mqtt_client.publish(Topics.ERROR, notif)

    def __do_copy_file(
        self,
        source_location: str,
        filepath: str,
        target_disk: str,
        target_location: str,
    ):
        source_fingerprint = FileHelper.calculate_fingerprint(
            f"{source_location}/{filepath}"
        )

        # Création du répertoire de destination si nécessaire
        parent_path = Path(filepath).parent
        if not parent_path.exists():
            print(f"Création du répertoire {parent_path} dans le dépôt")
            os.makedirs(f"{target_location}/{parent_path}", exist_ok=True)

        dest_fingerprint = FileHelper.copy_file(
            source_location, filepath, target_location, source_fingerprint
        )
        if dest_fingerprint != "":
            Logger().debug(
                f"The file {filepath} has been copied to {target_location}. The fingerprint is {source_fingerprint}"
            )

            # Envoi d'une notification pour informer de la présence d'un nouveau fichier
            notif = NotificationFactory.create_notification_new_file(
                disk=target_disk,
                filepath=filepath,
                source_fingerprint=source_fingerprint,
                dest_fingerprint=dest_fingerprint,
            )
            self.mqtt_client.publish(f"{Topics.NEW_FILE}/notification", notif)

            response = ResponseFactory.create_response_copy_file(
                filepath, target_disk, True, dest_fingerprint
            )
        else:
            response = ResponseFactory.create_response_copy_file(
                filepath, target_disk, False, dest_fingerprint
            )
            Logger().error(f"La copie du fichier {filepath} dans le dépôt a échoué.")

        self.mqtt_client.publish(f"{Topics.COPY_FILE}/response", response)

    def __handle_clear_queue(self):
        while not self.__copy_files_queue.empty():
            self.__copy_files_queue.get()

        while not self.__read_files_queue.empty():
            self.__read_files_queue.get()

    def __handle_mount_file(self, payload):
        """Mounts an archive file or a guest file (ISO, VMDK, etc)

        The guests files formats are not handled yet.
        The archives files formats list is provided by :data:`Constants.ARCHIVE_EXTENSIONS_HANDLED`.
        """

        if not MqttHelper.check_payload(payload, ["disk", "filepath"]):
            Logger().error(
                f"The command {Topics.MOUNT_FILE} misses argument(s)", "sys-usb"
            )
            return

        disk = payload["disk"]
        filepath = payload["filepath"]
        filename = self.sanitize_filename(os.path.basename(filepath))
        file_ext = "".join(Path(filename).suffixes)
        source_mount_point = Constants.USB_MOUNT_POINT
        file_mount_point = f"/media/loop/{filename}"

        if FileHelper.is_archive_file(filename):
            try:
                if os.path.exists(file_mount_point):
                    os.rmdir(file_mount_point)
                os.mkdir(file_mount_point, mode=0o770)
            except Exception as e:
                Logger().error(
                    f"An exception occured while preparing the mount point {file_mount_point}: {e}"
                )

            # The mount from python can not be done unless we are root... strange...
            cmd = [
                # "doas",
                # "/usr/bin/archivemount",
                "/usr/bin/fuse-archive",
                "-o",
                "nospecials",
                "-o",
                "noxattrs",
                "-o",
                "ro,nodev,nosuid,noexec",
                "-o",
                "uid=1000,gid=1000,umask=007",
                "-o",
                "allow_other",
                f"{source_mount_point}/{disk}{filepath}",
                f"{file_mount_point}",
            ]
            res = subprocess.run(cmd, check=False)

            if res.returncode == 0:
                payload = NotificationFactory.create_notification_disk_state(
                    filename, DiskState.MOUNTED
                )
                self.mqtt_client.publish(f"{Topics.DISK_STATE}", payload)
            else:
                Logger().warn(
                    f"The file {filepath} could not be mounted (exitcode={res.returncode}"
                )
        else:
            Logger().error(f"The file type {file_ext} is not handled for mounting")

    def __handle_unmount(self, payload):
        if not MqttHelper.check_payload(payload, ["disk"]):
            Logger().error(
                f"The command {Topics.MOUNT_FILE} misses argument(s)", "sys-usb"
            )
            return

        disk = payload["disk"]
        # file_mount_point =  f"/media/loop/{disk}"
        file_mount_point = FileHelper.get_mount_point(disk)

        if not file_mount_point:
            Logger().error(f"The disk {disk} is not mounted")
            return

        cmd = ["fusermount3", "-u", f"{file_mount_point}"]
        # cmd = [ "doas", "/bin/umount", f"{file_mount_point}" ]
        res = subprocess.run(cmd, check=False)

        if res.returncode == 0:
            # Mount succeeded, double check
            if not os.path.exists(file_mount_point):
                Logger().error(f"The disk {disk} has not been unmounted")
                return

            payload = NotificationFactory.create_notification_disk_state(
                disk, DiskState.UNMOUNTED
            )
            self.mqtt_client.publish(f"{Topics.DISK_STATE}", payload)

            try:
                os.rmdir(file_mount_point)
            except Exception as e:
                Logger().error(
                    f"Could not remove directory of mount point {file_mount_point}: {e}"
                )

    def sanitize_filename(self, s: str) -> str:
        """Replaces all non-printable chars of a filename with '_'"""

        result = []
        for c in s:
            if unicodedata.category(c)[0] == "C":
                result.append("_")
            else:
                result.append(c)

        return "".join(result).replace(" ", "_")

    ########
    ## Special functions
    ##
    def __debug_threads(self):
        print(f"Active threads: {threading.active_count()}")
        for thread in threading.enumerate():
            print(f"   -> {thread.name}")
