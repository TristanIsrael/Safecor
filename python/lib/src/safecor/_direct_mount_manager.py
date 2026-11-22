"""Direct USB mount manager.

Manages the direct USB mount from sys-usb via vchan+sshfs in a DomU.

Event-driven (NFR-3): the manager keeps a persistent MQTT client for the
whole process life and reacts to the bus events instead of polling:

- a one-shot ``my_config`` query determines the mount mode of the domain,
- the ``safecor_direct_mount`` component state (published by the sys-usb
  controller) triggers the mount (``READY``) or the unmount (``OFF``),
- a watchdog thread blocked on the sshfs process catches its death and
  remounts.

``/media/usb`` is mounted proactively at the end of the domain startup and
kept permanent, whether or not a USB disk is connected (the sshfs mount of
sys-usb's /media/usb directory succeeds even when empty).

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import signal
import subprocess
import sys
import threading
import time

from . import (
    Api,
    ComponentsHelper,
    ComponentState,
    Constants,
    Logger,
    MountMode,
    MqttFactory,
    System,
    Topics,
)

VCHAN_SFTP_SCRIPT_PATH = "/usr/local/bin/vchan-sftp"
MY_CONFIG_QUERY_TIMEOUT = 10  # seconds


class DirectMountManager:
    """Manages the direct USB mount from sys-usb via vchan+sshfs.

    This class runs in its own process (started by openrc). It keeps a
    persistent MQTT client for the whole process life and reacts to the
    events of the bus (NFR-3, no polling):

    - a one-shot ``my_config`` query determines the mount mode of the
      domain (a :class:`MountMode`),
    - the ``safecor_direct_mount`` component state (published by the
      sys-usb controller) triggers the mount (``READY``) or the unmount
      (``OFF``),
    - a watchdog thread blocked on the sshfs process catches its death
      and remounts.

    Product applications should use `System.is_usb_mountpoint_ready()` and
    `System.on_usb_mountpoint_ready(callback)` to check or wait for the
    mount to become available, rather than interacting with this class
    directly.

    .. seealso::
        :class:`System` - For mount point status queries
    """

    def __init__(self):
        self.__mounted = False
        self.__sshfs_process: subprocess.Popen | None = None
        self.__mount_mode: MountMode | None = None
        self.__component_state = ComponentState.UNKNOWN
        self.__disabled = False
        self.__running = False
        self.__requery_done = False

        self.__api = Api()
        self.__components = ComponentsHelper()
        self.__work_event = threading.Event()
        self.__my_config_event = threading.Event()

    def __log(self, level: str, message: str) -> None:
        """Logs a message and mirrors it on standard error.

        The openrc instance (``direct-mount``) redirects its output to
        ``/dev/null`` by default, and the MQTT log messages of this
        standalone process can be lost (short-lived client). The mirror on
        standard error is what makes a manually started process report its
        diagnostics on the domain console.
        """
        getattr(Logger(), level)(message)
        print(f"direct-mount: {message}", file=sys.stderr)

    def is_mounted(self) -> bool:
        """Returns True if the direct mount is active."""
        return self.__mounted

    def get_mount_point(self) -> str:
        """Returns the mount point path."""
        return Constants.USB_MOUNT_POINT

    def run(self) -> None:
        """Entry point for running as a standalone process.

        Keeps the MQTT client and the worker alive until a termination
        signal is received, or until the domain turns out to be not
        direct_mount (clean exit).
        """
        signal.signal(signal.SIGTERM, self.__handle_signal)
        signal.signal(signal.SIGINT, self.__handle_signal)

        self.__running = True
        self.__api.add_ready_callback(self.__on_ready)
        self.__api.add_message_callback(self.__on_message)
        self.__api.start(MqttFactory.create_mqtt_client_domu("direct-mount-manager"))

        threading.Thread(
            target=self.__worker_loop, name="dm-worker", daemon=True
        ).start()

        while self.__running:
            time.sleep(1)

    def stop(self) -> None:
        """Unmounts and cleans up the direct mount."""
        self.__running = False
        self.__unmount_mount()
        self.__log("info", "unmounted")

        try:
            self.__api.stop()
        except Exception:
            pass

        # Wake the worker so it can exit
        self.__work_event.set()

    def __handle_signal(self, signum, frame):
        """Handle SIGTERM/SIGINT: stop the mount and exit."""
        self.__log("info", "received termination signal")
        self.stop()
        sys.exit(0)

    ####
    # MQTT callbacks (fast, NFR-1): state updates only, the mount work is
    # delegated to the worker thread
    #
    def __on_ready(self) -> None:
        """Ready callback: one-shot fetch of the current state.

        Subscribes to the two topics of interest and issues the two
        one-shot requests allowed at subscribe time (NFR-3): the
        my_config query (the mount mode) and the discover_components
        request (the component states, covers the subscribe-after-publish
        race).
        """
        self.__api.subscribe(f"{Topics.MY_CONFIG}/response")
        self.__api.subscribe(f"{Topics.DISCOVER_COMPONENTS}/response")
        self.__api.discover_components()
        if self.__mount_mode is None and not self.__disabled:
            self.__query_my_config()

    def __on_message(self, topic: str, payload: dict) -> None:
        """Message callback: routes the bus events (state updates only)."""
        if topic == f"{Topics.MY_CONFIG}/response":
            self.__on_my_config_response(payload)
            return

        if topic == f"{Topics.DISCOVER_COMPONENTS}/response":
            self.__on_components_response(payload)
            return

    def __on_my_config_response(self, payload: dict) -> None:
        mode = self.__parse_mount_mode(payload)
        if mode is None:
            # The my_config response topic is shared by all the requesters
            # of the bus: a response for another domain is not ours.
            return

        self.__my_config_event.set()

        if mode is False:
            self.__disabled = True
            self.__work_event.set()
            return

        self.__mount_mode = mode
        self.__log("info", f"direct_mount enabled (mode={mode.value})")
        self.__work_event.set()

    def __on_components_response(self, payload: dict) -> None:
        self.__components.update(payload.get("components", []))
        state = self.__components.get_state(Constants.SAFECOR_DIRECT_MOUNT)

        if state != self.__component_state:
            self.__component_state = state

            # The component is the single synchronization point (NFR-3):
            # READY means the SFTP channels are up. If the my_config query
            # got no definitive answer yet, issue one event-triggered
            # one-shot re-query (bounded, not a retry loop).
            if (
                state == ComponentState.READY
                and self.__mount_mode is None
                and not self.__disabled
                and not self.__requery_done
            ):
                self.__requery_done = True
                self.__log(
                    "info",
                    "the safecor_direct_mount component is ready, "
                    "re-querying the direct mount configuration",
                )
                self.__query_my_config()

        self.__work_event.set()

    def __query_my_config(self) -> None:
        """Issues the one-shot my_config query (the mount mode of the domain).

        A dedicated watcher thread logs a one-shot warning if no
        definitive answer arrives within MY_CONFIG_QUERY_TIMEOUT (the
        bounded wait runs outside of the MQTT callbacks, NFR-1).
        """
        self.__my_config_event.clear()
        self.__api.publish(
            f"{Topics.MY_CONFIG}/request", {"domain_name": System.domain_name()}
        )
        threading.Thread(
            target=self.__watch_my_config, name="dm-my-config", daemon=True
        ).start()

    def __watch_my_config(self) -> None:
        """One-shot watcher: warns if the my_config query got no answer."""
        if not self.__my_config_event.wait(timeout=MY_CONFIG_QUERY_TIMEOUT):
            if self.__mount_mode is None and not self.__disabled:
                self.__log(
                    "warning",
                    "no my_config answer within "
                    f"{MY_CONFIG_QUERY_TIMEOUT} s, waiting for the "
                    "safecor_direct_mount component to be ready",
                )

    def __parse_mount_mode(self, payload: dict) -> MountMode | bool | None:
        """Extracts this domain's direct_mount mode from a my_config payload.

        Returns:
            The MountMode if the domain is enabled, False if the domain is
            present but not enabled, None if the domain is not in the
            payload (a response for another domain: no definitive answer).
        """
        domain_name = System.domain_name()
        for d in payload.get("domains", []):
            if d.get("name") != domain_name:
                continue
            dm = d.get("direct_mount")
            if not dm:
                return False
            raw_mode = dm.get("mode") if isinstance(dm, dict) else None
            if raw_mode == MountMode.RO.value:
                return MountMode.RO
            if raw_mode == MountMode.RW.value:
                return MountMode.RW
            self.__log("warning", f"invalid direct_mount mode {raw_mode!r}, using 'rw'")
            return MountMode.RW
        return None

    ####
    # The worker thread: the mount work, woken by the bus events
    #
    def __worker_loop(self) -> None:
        while self.__running:
            self.__work_event.wait(timeout=1.0)
            self.__work_event.clear()
            try:
                self.__do_work()
            except Exception as e:
                self.__log("error", f"the direct mount worker failed: {e}")

    def __do_work(self) -> None:
        """The mount decision, from the current (event-updated) state."""
        if not self.__running:
            return

        if self.__disabled:
            self.__log("info", "direct_mount is not enabled for this domain, exiting")
            self.stop()
            return

        state = self.__component_state

        if state == ComponentState.OFF:
            if self.__mounted or self.__sshfs_process is not None:
                self.__log("info", "the direct mount component is OFF, unmounting")
                self.__unmount_mount()
            return

        if (
            state == ComponentState.READY
            and self.__mount_mode is not None
            and not self.__mounted
        ):
            self.__log(
                "info",
                f"attempting to mount {Constants.USB_MOUNT_POINT} via sshfs",
            )
            if self.__generate_vchan_script() and self.__mount():
                self.__mounted = True
                self.__log(
                    "info",
                    f"{Constants.USB_MOUNT_POINT} mounted "
                    f"(mode={self.__mount_mode.value})",
                )
                self.__start_watchdog()

    def __start_watchdog(self) -> None:
        """The watchdog thread: blocked on the sshfs process (an event)."""
        threading.Thread(
            target=self.__watchdog, name="dm-watchdog", daemon=True
        ).start()

    def __watchdog(self) -> None:
        proc = self.__sshfs_process
        if proc is None:
            return
        proc.wait()
        if not self.__running or self.__disabled:
            return
        if self.__component_state == ComponentState.OFF:
            return
        self.__log("warning", "the sshfs process terminated, remounting")
        self.__mounted = False
        self.__work_event.set()

    ####
    # Mount mechanics
    #
    def __unmount_mount(self) -> None:
        """Terminates sshfs and unmounts the mount point."""
        if self.__sshfs_process is not None:
            try:
                self.__sshfs_process.terminate()
                self.__sshfs_process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    self.__sshfs_process.kill()
                except OSError:
                    pass
            self.__sshfs_process = None

        self.__unmount()
        self.__mounted = False

    def __sshfs_opts(self) -> str:
        """The sshfs options of the direct mount.

        reconnect: re-establish the SFTP session on connection loss, so
        the mount heals itself when the channel drops (complements the
        watchdog).
        """
        opts = (
            f"ssh_command={VCHAN_SFTP_SCRIPT_PATH},"
            "noexec,nosuid,nodev,default_permissions,max_read=131072,reconnect"
        )
        if self.__mount_mode == MountMode.RO:
            opts += ",ro"
        return opts

    def __generate_vchan_script(self) -> bool:
        """Generate the vchan-socket-proxy client script.

        The peer (sys-usb) domid is resolved at runtime so the script stays
        valid when sys-usb is restarted with a different domid. The vchan
        channel data lives in the shared xenstore namespace
        /local/domain/system/vchan/<domain>/<channel>, which is readable by
        all DomUs (a DomU cannot read /local/domain/0).
        """
        try:
            os.makedirs(os.path.dirname(VCHAN_SFTP_SCRIPT_PATH), exist_ok=True)
            content = (
                "#!/bin/sh\n"
                "exec vchan-socket-proxy -m client "
                "$(xenstore-read /local/domain/system/domids/sys-usb) "
                "/local/domain/system/vchan/$(hostname)/sftp -\n"
            )
            with open(VCHAN_SFTP_SCRIPT_PATH, "w") as f:
                f.write(content)
            os.chmod(VCHAN_SFTP_SCRIPT_PATH, 0o755)
            return True
        except OSError as e:
            self.__log("warning", f"cannot write the vchan script: {e}")
            return False

    def __mount(self) -> bool:
        """Mount the USB folder via sshfs over vchan."""
        mount_point = Constants.USB_MOUNT_POINT
        try:
            os.makedirs(mount_point, exist_ok=True)
        except OSError as e:
            self.__log("warning", f"cannot create the mount point: {e}")
            return False

        try:
            self.__sshfs_process = subprocess.Popen(
                ["sshfs", "-f", "-o", self.__sshfs_opts(), "none:/", mount_point],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, FileNotFoundError) as e:
            self.__log("warning", f"sshfs failed to start: {e}")
            self.__sshfs_process = None
            return False

        # Give it a moment to establish
        time.sleep(2)
        if self.__sshfs_process.poll() is None:
            return True

        self.__log(
            "warning",
            f"sshfs exited with code {self.__sshfs_process.returncode}",
        )
        self.__sshfs_process = None
        return False

    def __unmount(self) -> None:
        """Unmount the sshfs mount point."""
        mount_point = Constants.USB_MOUNT_POINT
        try:
            subprocess.run(["fusermount", "-u", mount_point], timeout=10)
        except (subprocess.SubprocessError, OSError):
            try:
                subprocess.run(["umount", mount_point], timeout=10)
            except (subprocess.SubprocessError, OSError):
                pass
