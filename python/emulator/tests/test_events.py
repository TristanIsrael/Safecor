"""Tests for the thread-safe, bounded event bus (:mod:`safecor_emulator.events`)."""

import threading

import pytest
from safecor_emulator.events import (
    STREAMS,
    Event,
    EventBus,
    FileRecorder,
)


def test_streams_are_the_three_expected():
    assert set(STREAMS) == {"actions", "mqtt_events", "platform_log"}


def test_publish_stores_an_event():
    bus = EventBus()
    entry = bus.publish("actions", "console", "start_emulator", {"a": 1})
    assert isinstance(entry, Event)
    assert entry.source == "console"
    assert entry.text == "start_emulator"
    assert entry.payload == {"a": 1}
    assert entry.timestamp > 0

    entries = bus.entries("actions")
    assert len(entries) == 1
    assert entries[0] is entry


def test_publish_rejects_unknown_stream():
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.publish("nope", "src", "text")
    with pytest.raises(ValueError):
        bus.entries("nope")
    with pytest.raises(ValueError):
        bus.subscribe("nope", lambda e: None)


def test_streams_are_independent():
    bus = EventBus()
    bus.publish("actions", "s", "a")
    bus.publish("mqtt_events", "s", "m")
    bus.publish("platform_log", "s", "l")
    assert len(bus.entries("actions")) == 1
    assert len(bus.entries("mqtt_events")) == 1
    assert len(bus.entries("platform_log")) == 1
    assert len(bus) == 3


def test_subscribe_receives_new_entries_only():
    bus = EventBus()
    # Published before the subscription: must not be replayed to the subscriber.
    bus.publish("actions", "s", "before")

    seen = []
    bus.subscribe("actions", seen.append)
    assert seen == []

    bus.publish("actions", "s", "after")
    assert [e.text for e in seen] == ["after"]


def test_subscribe_multiple_and_unsubscribe():
    bus = EventBus()
    a, b = [], []
    bus.subscribe("actions", a.append)
    bus.subscribe("actions", b.append)
    bus.publish("actions", "s", "x")
    assert len(a) == 1 and len(b) == 1

    bus.unsubscribe("actions", a.append)
    bus.publish("actions", "s", "y")
    assert len(a) == 1 and len(b) == 2


def test_stream_is_bounded():
    bus = EventBus(maxlen=3)
    for i in range(10):
        bus.publish("actions", "s", f"e{i}")
    # Only the last 3 entries are kept, in order.
    assert [e.text for e in bus.entries("actions")] == ["e7", "e8", "e9"]


def test_clear_one_and_all():
    bus = EventBus()
    bus.publish("actions", "s", "a")
    bus.publish("mqtt_events", "s", "m")
    bus.clear("actions")
    assert len(bus.entries("actions")) == 0
    assert len(bus.entries("mqtt_events")) == 1

    bus.clear()
    assert len(bus) == 0


def test_publish_is_thread_safe():
    bus = EventBus()
    count = 0

    def worker():
        nonlocal count
        for _ in range(100):
            bus.publish("actions", "t", "x")
            count += 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert count == 800
    assert len(bus.entries("actions")) == 800
    assert len(bus) == 800


def test_file_recorder_appends_json_lines(tmp_path):
    path = str(tmp_path / "rec.jsonl")
    bus = EventBus()
    recorder = FileRecorder(path)
    bus.subscribe("mqtt_events", recorder)
    try:
        bus.publish("mqtt_events", "Dom0", "PUBLISH system/x", {"k": "v"})
        bus.publish("mqtt_events", "Dom0", "PUBLISH system/y", [1, 2])
    finally:
        recorder.close()

    lines = open(path, encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    import json

    first = json.loads(lines[0])
    assert first["source"] == "Dom0"
    assert first["text"] == "PUBLISH system/x"
    assert first["payload"] == {"k": "v"}
    assert "timestamp" in first
