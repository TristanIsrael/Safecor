"""A thread-safe, bounded event bus for the operator console.

The console observes three independent streams:

- ``actions``      -- scenario steps triggered by the operator,
- ``mqtt_events``  -- requests handled / notifications published by the mocks,
- ``platform_log`` -- captured platform log lines.

Every entry is an :class:`Event` (timestamp, source, human text, raw payload).
Each stream is a fixed-size ring buffer, so a long session cannot grow memory
without bound. Consumers subscribe a callback, invoked (on the publishing
thread) for every new entry. The bus is pure Python: it has no Qt dependency,
so it can be tested headlessly.
"""

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List, Optional

#: The three event streams exposed by the bus.
STREAMS = ("actions", "mqtt_events", "platform_log")


@dataclass
class Event:
    """A single bus entry."""

    timestamp: float
    source: str
    text: str
    payload: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-friendly representation (for :class:`FileRecorder`)."""
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "text": self.text,
            "payload": self.payload,
        }


class EventBus:
    """A thread-safe, bounded bus with three named streams."""

    def __init__(self, maxlen: int = 1000):
        self._maxlen = maxlen
        self._streams: Dict[str, Deque[Event]] = {
            s: deque(maxlen=maxlen) for s in STREAMS
        }
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {
            s: [] for s in STREAMS
        }
        self._lock = threading.RLock()

    def publish(
        self, stream: str, source: str, text: str, payload: Any = None
    ) -> Event:
        """Append an entry to ``stream`` and notify its subscribers.

        :param stream: one of :data:`STREAMS`.
        :param source: name of the publisher (e.g. ``"Dom0"``).
        :param text: human-readable description of the event.
        :param payload: optional raw payload (topic payload, arguments, ...).
        :return: the :class:`Event` that was recorded.
        """
        if stream not in self._streams:
            raise ValueError(f"Unknown stream: {stream!r} (expected one of {STREAMS})")
        entry = Event(time.time(), source, text, payload)
        with self._lock:
            self._streams[stream].append(entry)
            callbacks = list(self._subscribers[stream])
        for callback in callbacks:
            callback(entry)
        return entry

    def subscribe(self, stream: str, callback: Callable[[Event], None]) -> None:
        """Subscribe ``callback`` to every new entry of ``stream``."""
        if stream not in self._streams:
            raise ValueError(f"Unknown stream: {stream!r}")
        with self._lock:
            self._subscribers[stream].append(callback)

    def unsubscribe(self, stream: str, callback: Callable[[Event], None]) -> None:
        """Remove a previously subscribed callback (no-op if absent)."""
        with self._lock:
            if callback in self._subscribers[stream]:
                self._subscribers[stream].remove(callback)

    def entries(self, stream: str) -> List[Event]:
        """A snapshot of the entries currently held for ``stream``."""
        if stream not in self._streams:
            raise ValueError(f"Unknown stream: {stream!r}")
        with self._lock:
            return list(self._streams[stream])

    def clear(self, stream: Optional[str] = None) -> None:
        """Clear one stream, or all of them when ``stream`` is None."""
        with self._lock:
            if stream is None:
                for s in STREAMS:
                    self._streams[s].clear()
            else:
                self._streams[stream].clear()

    def __len__(self) -> int:
        """Total number of entries across all streams."""
        with self._lock:
            return sum(len(d) for d in self._streams.values())


class FileRecorder:
    """Append the entries of a bus stream to a file as JSON lines.

    Intended to be used as a bus subscriber (see :meth:`EventBus.subscribe`),
    so every new entry of the subscribed stream is appended to ``path``.
    """

    def __init__(self, path: str):
        self.path = path
        self._fh = open(path, "a", encoding="utf-8")

    def __call__(self, event: Event) -> None:
        """Append ``event`` to the file as a JSON line (invoked by the bus)."""
        self._fh.write(json.dumps(event.to_dict(), default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        """Flush and close the underlying file handle (idempotent)."""
        try:
            self._fh.close()
        except Exception:
            pass
