"""XenStore

High-level, non-CLI access to the XenStore tree through the Xen Python
bindings (``xen.lowlevel.xs``, i.e. libxenstore).  It replaces the
``xenstore-read`` / ``xenstore-write`` / ``xenstore-ls`` subprocess calls:
no process is spawned and no ``doas`` grant is needed — the access rights
are the standard XenStore per-domain grants, set up by
``set-xenstore-permissions.sh`` (see the orchestrator component and ADR 0006).

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

from enum import Enum
from threading import Thread
from typing import Callable, Optional

import xen.lowlevel.xs as xapi

from . import SysLogger


class XsDomain(Enum):
    """Well-known XenStore domain aliases."""

    System = "system"
    SysUsb = "sys-usb"


class XsKey(Enum):
    """Well-known XenStore keys."""

    InputFocus = "input-focus"


class XenStore:
    """Reads, writes and watches nodes of the XenStore.

    Each instance opens its own XenStore connection (``xen.lowlevel.xs``)
    and keeps its own monitoring state: instances are independent, this
    class is **not** a singleton.

    The access rights follow the XenStore per-domain model: in Dom0 the
    whole tree is accessible; in a DomU, the domain sees its own subtree
    (``/local/domain/<own domid>``) plus whatever Dom0 grants on shared
    paths such as ``/local/domain/system`` (see
    ``set-xenstore-permissions.sh`` and ADR 0006).
    """

    def __init__(self):
        self.__xs = xapi.xs()
        # Per-instance monitoring state (see monitor()):
        # token -> (callback, key_path, parent_path)
        self.__watches: dict = {}
        self.__monitoring_running = False
        self.__can_run = False

    def read(self, domain_name: str, key: str) -> Optional[str]:
        """Reads a key of a domain's XenStore subtree.

        The domain is resolved with ``__get_domain_id``: ``"system"``
        targets the shared system subtree (``/local/domain/system``), any
        other name is resolved through the domid cache
        (``/local/domain/system/domids/<name>``).

        Args:
            domain_name: The domain alias (see :class:`XsDomain`) or name
                (e.g. ``"sys-usb"``).
            key: The key path, relative to the domain subtree (e.g.
                ``"domids/sys-usb"`` or ``"name"``).

        Returns:
            The node value as a string, or ``None`` when the node does not
            exist, the domain cannot be resolved, or the node is not
            readable from the current domain (per-domain XenStore grants).
        """

        dom_id = self.__get_domain_id(domain_name)
        path = f"/local/domain/{dom_id}/{key}"
        return self.read_path(path)

    def read_path(self, key_path: str) -> Optional[str]:
        """Reads a XenStore node from an absolute path.

        Args:
            key_path: The absolute path of the node (e.g.
                ``"/local/domain/system/domids/sys-usb"``).

        Returns:
            The node value as a string, or ``None`` when the node does not
            exist (or is not readable from the current domain).
        """

        txn_id = self.__start_transaction()
        val = self.__xs.read(txn_id, f"{key_path}")
        self.__end_transaction(txn_id)

        if val is None:
            return None
        return val.decode()

    def read_children(self, key_path: str) -> list:
        """Lists the direct children of a XenStore node (equivalent of
        ``xenstore-ls <path>``).

        Args:
            key_path: The absolute path of the directory node (e.g.
                ``"/local/domain"``).

        Returns:
            The list of child names (strings), or an empty list when the
            node does not exist (or is not readable from the current
            domain).
        """

        txn_id = self.__start_transaction()
        children = self.__xs.read_dir(txn_id, f"{key_path}")
        self.__end_transaction(txn_id)

        if not children:
            return []
        # The binding may return str or bytes entries depending on the Xen
        # version; normalize to str.
        return [c.decode() if isinstance(c, bytes) else c for c in children]

    def write(self, domain_name: str, key: str, value: str) -> bool:
        """Writes a value in the XenStore.

        The domain is resolved with ``__get_domain_id`` (see :meth:`read`).

        Args:
            domain_name: The domain alias (see :class:`XsDomain`) or name.
            key: The key path, relative to the domain subtree.
            value: The value to store.

        Returns:
            ``True`` when the write was committed, ``False`` on failure
            (the error is logged in that case).
        """

        dom_id = self.__get_domain_id(domain_name)
        txn_id = self.__start_transaction()

        try:
            self.__xs.write(txn_id, f"/local/domain/{dom_id}/{key}", value)
            self.__end_transaction(txn_id, False)
            return True
        except Exception as e:
            self.__end_transaction(txn_id, True)
            SysLogger("XenStore").error(f"Could not write to the XenStore: {str(e)}")
            SysLogger("XenStore").error(
                f"domain_name={domain_name}, dom_id={dom_id}, key={key}, value={value}"
            )
            return False

    def monitor(
        self,
        domain_name: str,
        key: str,
        token: str,
        callback: Callable[[Optional[str]], None],
    ) -> None:
        """Watches a key and invokes *callback* on every change.

        XenStore watches are attached to nodes, so the implementation keeps
        the watch alive across the node's whole lifetime:

        - the key exists → a watch is set on the key itself (value changes);
        - the key does not exist (yet) → a watch is set on its parent
          directory, which fires when the key is created;
        - on every event the watch is re-synchronized: the key exists →
          watch on the key; the key was deleted (a node's watch dies with
          the node) → back to the parent, so a re-creation is still caught.

        The callback receives the **current value** of the key (``str``) or
        ``None`` when the key does not exist at event time (a warning is
        logged, monitoring continues).  Note that a directory watch also
        fires when a *sibling* node changes, so the callback may be invoked
        with an unchanged value; callers that care must deduplicate.

        The callback runs in this instance's watch reader thread: keep it
        short and non-blocking.  Watch registration (``xs.watch``) may raise
        when the current domain lacks the tell permission on the node.

        Args:
            domain_name: The domain alias (see :class:`XsDomain`) or name
                (see :meth:`read`).
            key: The key path, relative to the domain subtree.
            token: A unique token identifying this watch (used to dispatch
                events back to *callback*).
            callback: Invoked with the current key value (``str``) or
                ``None`` (key absent).
        """

        key_path = f"/local/domain/{self.__get_domain_id(domain_name)}/{key}"
        parent_path = key_path.rsplit("/", 1)[0] or "/"
        self.__watches[token] = (callback, key_path, parent_path)
        self.__sync_watches(token)

        if not self.__monitoring_running:
            self.__can_run = True
            Thread(target=self.__do_monitor, daemon=True).start()

    def stop(self) -> None:
        """Stops the dispatch of monitoring callbacks.

        The reader thread is a daemon: it ends at the next watch event (it
        cannot be interrupted while blocked waiting for an event) or when
        the process exits.
        """

        self.__can_run = False

    def __do_monitor(self) -> None:
        """Watch reader loop (runs in this instance's own thread).

        Waits for XenStore watch events and dispatches each one to the
        registered callback with the current value of the watched key.
        A missing key is not an error: the callback is invoked with
        ``None`` and the monitoring continues.
        """

        self.__monitoring_running = True

        while self.__can_run:
            try:
                path, token = self.__xs.read_watch()
            except Exception:
                # The connection is gone (e.g. shutdown): the watch queue no
                # longer exists, stop dispatching.
                break
            if not self.__can_run:
                # stop() was called while waiting: drop the event.
                break

            try:
                if token not in self.__watches:
                    continue
                callback, key_path, _parent_path = self.__watches[token]
                value = self.read_path(key_path)
                # Re-attach the watch to the right node (it may have died
                # with a deleted node).
                self.__sync_watches(token)
                if value is None:
                    SysLogger("XenStore").warn(
                        f"No value found in XenStore for {key_path}"
                    )
                callback(value)
            except Exception as e:
                SysLogger("XenStore").error(f"Monitoring error: {str(e)}")

    def __sync_watches(self, token: str) -> None:
        """(Re)attaches the watch of *token* to the right node.

        The key exists → watch on the key; the key is absent → watch on its
        parent directory (a XenStore watch cannot be set on a missing node,
        and a node's watch dies when the node is deleted).  Setting a watch
        with the same (path, token) pair is idempotent.
        """

        _callback, key_path, parent_path = self.__watches[token]
        if self.read_path(key_path) is not None:
            self.__xs.watch(key_path, token)
        else:
            self.__xs.watch(parent_path, token)

    def __get_domain_id(self, domain_name: str) -> str:
        """Resolves a domain name to its XenStore path component.

        ``"system"`` maps to the shared system subtree.  Any other name is
        resolved through the domid cache at
        ``/local/domain/system/domids/<name>`` — the Dom0-maintained
        convenience cache, self-healed per ADR 0006 (the same source as the
        former ``System.get_domain_domid``).

        Args:
            domain_name: The domain name (e.g. ``"system"``, ``"sys-usb"``).

        Returns:
            The path component to use under ``/local/domain/`` (``"system"``
            or the domid as a string), or ``""`` when the domain is unknown:
            the resulting path is invalid and the operation fails
            gracefully (``None`` on read, ``False`` on write).
        """

        if domain_name == XsDomain.System.value:
            return XsDomain.System.value

        cached = self.read_path(f"/local/domain/system/domids/{domain_name}")
        return cached.strip() if cached else ""

    def __start_transaction(self) -> int:
        """Starts a transaction for reading or writing."""

        return self.__xs.transaction_start()

    def __end_transaction(self, transaction_id: int, abort: bool = False):
        """Ends a transaction after a read or a write."""

        return self.__xs.transaction_end(transaction_id, abort)
