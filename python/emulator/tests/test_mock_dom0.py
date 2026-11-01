"""Tests for the mock Dom0 workflow/GUI fakes (W2, W4, W5) and the event bus.

These run a real :class:`Emulator` (broker + mock peers) and exercise the new
scenario helpers, asserting both the MQTT response and the event-bus entries
produced by the instrumented peers.
"""

import pytest

from safecor_emulator import Emulator


@pytest.fixture
def em(tmp_path):
    disk = tmp_path / "d0"
    disk.mkdir()
    emulator = Emulator(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    emulator.start()
    yield emulator
    emulator.stop()


def _mqtt_texts(em):
    return [e.text for e in em.event_bus.entries("mqtt_events")]


def _log_texts(em):
    return [e.text for e in em.event_bus.entries("platform_log")]


def test_shutdown_fake_is_accepted_and_recorded(em):
    resp = em.shutdown()
    assert resp is not None
    assert resp.get("state") == "accepted"

    assert any("workflow/shutdown" in t for t in _mqtt_texts(em))
    assert any("shutdown" in t.lower() for t in _log_texts(em))


def test_gui_ready_fake_is_accepted_and_recorded(em):
    resp = em.gui_ready()
    assert resp is not None
    assert resp.get("accepted") is True

    assert any("gui_ready" in t for t in _mqtt_texts(em))
    assert any("GUI ready" in t for t in _log_texts(em))


def test_switch_gui_fake_is_accepted_and_recorded(em):
    resp = em.switch_gui("saphir-gui")
    assert resp is not None
    assert resp.get("state") == "accepted"

    assert any("gui/switch" in t for t in _mqtt_texts(em))
    assert any("saphir-gui" in t for t in _log_texts(em))


def test_ping_roundtrip_over_broker(em):
    resp = em.ping("Dom0", "hello")
    assert resp is not None
    assert resp.get("source") == "Dom0"
    assert resp.get("data") == "hello"
    assert resp.get("id", "").startswith("emul-")
