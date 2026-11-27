"""In-memory ``xen.lowlevel.xs`` replacement (see the package docstring).

The tree is module-global so that every connection handle in the process
sees the same state.  ``safecor_emulator.activate.install_fakes`` seeds it
(screen size, screen rotation, the domid convenience cache — ADR 0006).
"""

import threading

# Module-global state: path -> value (str).
_tree: dict[str, str] = {}
# (path, token) -> True
_watches: dict[tuple[str, str], bool] = {}
# Pending watch events: (path, token)
_events: list[tuple[str, str]] = []
_lock = threading.Lock()


def set_tree(tree: dict[str, str]) -> None:
    """Replaces the whole in-memory tree (drops watches and pending events)."""

    global _tree, _watches, _events
    with _lock:
        _tree = dict(tree)
        _watches = {}
        _events = []


def get_tree() -> dict[str, str]:
    """Returns a copy of the current tree."""

    with _lock:
        return dict(_tree)


def notify(path: str, token: str) -> None:
    """Enqueues a watch event (test helper)."""

    with _lock:
        _events.append((path, token))


class xs:
    """An in-memory XenStore connection."""

    def transaction_start(self) -> int:
        return 1

    def transaction_end(self, txn: int, abort: bool = False) -> int:
        return 0

    def read(self, txn: int, path: str):
        """Returns the node value as bytes, or None when absent."""

        with _lock:
            value = _tree.get(path)
        return None if value is None else value.encode()

    def read_dir(self, txn: int, path: str):
        """Returns the sorted list of direct child names, or None."""

        prefix = path.rstrip("/") + "/"
        with _lock:
            children = {
                key[len(prefix) :].split("/", 1)[0]
                for key in _tree
                if key.startswith(prefix)
            }
        return sorted(children) or None

    def write(self, txn: int, path: str, value: str) -> None:
        # Mirror libxenstore: an empty path component is rejected.
        if "//" in path:
            raise OSError("invalid path")
        with _lock:
            _tree[path] = value

    def watch(self, path: str, token: str) -> None:
        with _lock:
            _watches[(path, token)] = True

    def read_watch(self):
        """Blocks (polling) until a watch event arrives, like the real
        binding.  The calling thread is a daemon in the library."""

        while True:
            with _lock:
                if _events:
                    return _events.pop(0)
            threading.Event().wait(0.01)
