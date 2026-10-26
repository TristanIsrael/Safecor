"""Manage a local Mosquitto broker for the emulated core.

The emulator uses an external ``mosquitto`` process (chosen over an in-process
broker). The ``safecor`` MQTT client connects to the default MQTT port (1883)
in TCP mode, so the emulated broker must run on that port. The orchestrator
(:class:`safecor_emulator.Emulator`) reuses a broker already listening on 1883
and only starts its own otherwise.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def broker_is_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    """Returns True if something (presumably an MQTT broker) listens on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


class MosquittoBroker:
    """A local Mosquitto broker whose lifetime is managed here.

    Note: the ``safecor`` MQTT client connects to the default MQTT port (1883)
    in TCP mode, so the emulated broker must run on that port (or an existing
    broker on 1883 must be reused). See :class:`safecor_emulator.Emulator`.
    """

    def __init__(self, port: int = 1883, host: str = "localhost",
                 unix_socket: str = None, workdir: str = None):
        self.port = port
        self.host = host
        self.unix_socket = unix_socket
        self._workdir = Path(workdir) if workdir else Path(
            tempfile.mkdtemp(prefix="safecor_emulator_mosq_"))
        self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _write_config(self) -> Path:
        self._workdir.mkdir(parents=True, exist_ok=True)
        lines = [
            f"pid_file {self._workdir / 'mosquitto.pid'}",
            "log_dest none",
            "allow_anonymous true",
            f"listener {self.port}",
        ]
        if self.unix_socket:
            sock_dir = os.path.dirname(self.unix_socket)
            if sock_dir:
                os.makedirs(sock_dir, exist_ok=True)
            lines.append(f"listener {self.unix_socket}")
        config = self._workdir / "mosquitto.conf"
        config.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config

    def start(self, timeout: float = 10.0):
        """Start the broker and wait until the TCP port is reachable."""
        if self.is_running:
            return
        mosquitto = shutil.which("mosquitto")
        if mosquitto is None:
            raise RuntimeError(
                "The 'mosquitto' executable was not found on PATH. "
                "Install it (e.g. 'apt-get install mosquitto') to use the "
                "safecor emulator.")

        config = self._write_config()
        logfile = self._workdir / "mosquitto.log"
        with open(logfile, "ab") as lf:
            self._proc = subprocess.Popen(
                [mosquitto, "-c", str(config)],
                stdout=lf, stderr=lf, stdin=subprocess.DEVNULL,
            )

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"mosquitto exited early (code={self._proc.returncode}). "
                    f"See log: {logfile}")
            if _port_is_open(self.host, self.port):
                return
            time.sleep(0.1)

        self.stop()
        raise RuntimeError(f"mosquitto did not open port {self.port} "
                           f"within {timeout}s. See log: {logfile}")

    def stop(self):
        """Stop the broker (best effort)."""
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
        self._proc = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
