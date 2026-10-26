"""Fake input device for the emulator.

On real hardware, keyboard/mouse events are read by ``safecor.InputsDaemon``
from a XenBus serial socket and forwarded as a *msgpack-packed* 4-tuple
``[input_type, evdev_type, evdev_code, evdev_value]`` terminated by a newline
(see ``InputsDaemon.__serialize_event``). There is no MQTT topic for input.

This class is the software stand-in for that input channel on a machine without
Xen. It serializes events with the *exact same wire format* and writes them to a
local file, which can then be consumed by whatever stands in for the DomU input
socket (e.g. point ``Constants.DOMU_INPUT_SOCKET_FILEPATH`` at that file).

It has **no hard dependency** on ``evdev``/``ecodes`` (which are optional): the
common Linux input event codes are defined here directly.
"""

import os
from typing import List, Tuple, Union

import msgpack

from safecor import InputType

# --- Linux input event constants (input-event-codes.h) ---------------------
EV_SYN = 0
EV_KEY = 1
EV_REL = 2
EV_ABS = 3
EV_MSC = 4

REL_X = 0
REL_Y = 1
REL_WHEEL = 8

BTN_LEFT = 0x110
BTN_MIDDLE = 0x112
BTN_RIGHT = 0x111

_KEY_CODES = {
    "esc": 1, "escape": 1,
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35, "i": 23,
    "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25, "q": 16, "r": 19,
    "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
    "enter": 28, "return": 28, "tab": 15, "backspace": 14, "space": 57,
    "shift": 42, "ctrl": 29, "alt": 56,
    "up": 103, "left": 105, "right": 106, "down": 108,
    "delete": 111, "home": 102, "end": 107,
}

_BUTTONS = {"left": BTN_LEFT, "middle": BTN_MIDDLE, "right": BTN_RIGHT}


class FakeInputDevice:
    """Produces input events in the XenBus wire format and writes them to a file.

    :param output_path: file where the serialized (msgpack) events are appended.
    """

    def __init__(self, output_path: str):
        self._path = output_path
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    @property
    def path(self) -> str:
        """Path of the file holding the serialized input events."""
        return self._path

    def _write(self, event: List[int]):
        data = msgpack.packb(event) + b"\n"
        with open(self._path, "ab") as f:
            f.write(data)

    @staticmethod
    def _resolve_key(key: Union[str, int]) -> int:
        if isinstance(key, int):
            return key
        code = _KEY_CODES.get(str(key).lower())
        if code is None:
            raise ValueError(f"Unknown key {key!r}")
        return code

    # --- keyboard ----------------------------------------------------------
    def inject_key(self, key: Union[str, int], pressed: bool = True):
        """Emit a key press (``pressed=True``) or release (``pressed=False``)."""
        self._write([InputType.KEYBOARD, EV_KEY, self._resolve_key(key), 1 if pressed else 0])

    def press_key(self, key: Union[str, int]):
        """Emit a key press."""
        self.inject_key(key, pressed=True)

    def release_key(self, key: Union[str, int]):
        """Emit a key release."""
        self.inject_key(key, pressed=False)

    def click(self, key: Union[str, int]):
        """Emit a full key click (press + release)."""
        self.press_key(key)
        self.release_key(key)

    # --- mouse -------------------------------------------------------------
    def mouse_move(self, dx: int = 0, dy: int = 0):
        """Emit a relative mouse movement followed by a sync event."""
        self._write([InputType.MOUSE, EV_REL, REL_X, dx])
        self._write([InputType.MOUSE, EV_REL, REL_Y, dy])
        self._write([InputType.MOUSE, EV_SYN, 0, 0])

    def mouse_button(self, button: Union[str, int], pressed: bool = True):
        """Emit a mouse button press/release followed by a sync event."""
        code = button if isinstance(button, int) else _BUTTONS.get(str(button).lower())
        if code is None:
            raise ValueError(f"Unknown mouse button {button!r}")
        self._write([InputType.MOUSE, EV_KEY, code, 1 if pressed else 0])
        self._write([InputType.MOUSE, EV_SYN, 0, 0])

    def mouse_click(self, button: Union[str, int] = "left"):
        """Emit a full mouse click (press + release)."""
        self.mouse_button(button, pressed=True)
        self.mouse_button(button, pressed=False)

    def mouse_wheel(self, delta: int):
        """Emit a mouse wheel movement followed by a sync event."""
        self._write([InputType.MOUSE, EV_REL, REL_WHEEL, delta])
        self._write([InputType.MOUSE, EV_SYN, 0, 0])

    # --- generic / inspection ---------------------------------------------
    def write_raw(self, event: List[int]):
        """Write an arbitrary 4-tuple ``[input_type, type, code, value]``."""
        self._write(list(event))

    def read_events(self) -> List[List[int]]:
        """Read back the serialized events (useful for tests and inspection)."""
        events: List[List[int]] = []
        if not os.path.exists(self._path):
            return events
        with open(self._path, "rb") as f:
            for line in f.read().split(b"\n"):
                if line:
                    events.append(msgpack.unpackb(line))
        return events
