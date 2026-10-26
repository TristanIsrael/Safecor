"""Tests for the P2 features: USB hot-plug and fake input.

These use the session ``emulator`` fixture provided by
``safecor_emulator.pytest_plugin`` (see conftest.py).
"""

import time
import threading

from safecor import MqttClient, ConnectionType, Topics
from safecor_emulator import FakeInputDevice


def test_hot_plug_disk_state(emulator, tmp_path):
    """Attaching/detaching a disk emits the right DISK_STATE notifications."""
    got = {}
    got_ev = threading.Event()

    client = MqttClient("hotplug-test", ConnectionType.TCP_DEBUG, "localhost")
    client.on_connected = lambda: client.subscribe(Topics.DISK_STATE)
    client.on_message = lambda topic, payload: (got.update(payload), got_ev.set())
    client.start()
    time.sleep(0.5)  # let it connect and subscribe

    hot = tmp_path / "hotdisk"
    hot.mkdir()
    emulator.attach_disk("hot", str(hot))
    assert got_ev.wait(10), "no DISK_STATE notification on attach"
    assert got.get("disk") == "hot"
    assert got.get("state") == "connected"

    got.clear()
    got_ev.clear()
    emulator.detach_disk("hot")
    assert got_ev.wait(10), "no DISK_STATE notification on detach"
    assert got.get("disk") == "hot"
    assert got.get("state") == "disconnected"

    client.stop()


def test_fake_input_via_emulator(emulator):
    """Emulator.inject_key / mouse_move serialize into the input channel file."""
    before = len(emulator.input.read_events())
    emulator.inject_key("a")
    emulator.mouse_move(3, 4)
    events = emulator.input.read_events()[before:]
    # 'a' press: [InputType.KEYBOARD, EV_KEY, KEY_A, pressed]
    assert events[0] == [1, 1, 30, 1]
    # mouse move: REL_X, REL_Y, EV_SYN
    assert events[-3:] == [[2, 2, 0, 3], [2, 2, 1, 4], [2, 0, 0, 0]]


def test_fake_input_wire_format_standalone(tmp_path):
    """FakeInputDevice emits the exact XenBus wire format (msgpack 4-tuple)."""
    dev = FakeInputDevice(str(tmp_path / "in.events"))
    dev.click("a")
    dev.mouse_click("left")
    events = dev.read_events()
    # key 'a' (code 30) press + release
    assert events[0] == [1, 1, 30, 1]
    assert events[1] == [1, 1, 30, 0]
    # left button (0x110) press + sync + release + sync
    assert events[2] == [2, 1, 0x110, 1]
    assert events[3] == [2, 0, 0, 0]
    assert events[4] == [2, 1, 0x110, 0]
    assert events[5] == [2, 0, 0, 0]
