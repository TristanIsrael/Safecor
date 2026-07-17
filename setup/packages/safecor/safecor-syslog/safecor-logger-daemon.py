import os
import socket
import logging
from safecor import Logger

SOCKET_PATH = "/var/run/safecor_logger.sock"

SEVERITY = {
    0: logging.CRITICAL,
    1: logging.CRITICAL,
    2: logging.CRITICAL,
    3: logging.ERROR,
    4: logging.WARNING,
    5: logging.WARNING,
    6: logging.INFO,
    7: logging.DEBUG
}

try:
    os.unlink(SOCKET_PATH)
except FileNotFoundError:
    pass

with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
    s.bind(SOCKET_PATH)

    while True:
        data = s.recv(1024)
        if data and b'-' in data:
            parts = data.split(b' - ', 1)
            severity = parts[0].decode().strip()
            msg = parts[1].decode().strip()

            safecor_severity = SEVERITY.get(severity, logging.WARNING)

            if safecor_severity == logging.DEBUG:
                Logger().debug(msg)
            elif safecor_severity == logging.INFO:
                Logger().info(msg)
            elif safecor_severity == logging.WARNING:
                Logger().warning(msg)
            elif safecor_severity == logging.ERROR:
                Logger().error(msg)
            elif safecor_severity == logging.CRITICAL:
                Logger().critical(msg)
