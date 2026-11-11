"""
utils/mailbox.py — single-slot, thread-safe hand-off that keeps only the newest item.

The detection worker posts a status every frame; the Tk thread polls and applies
only the latest one. This keeps the worker from ever calling into Tk (which
blocks while the Tk thread is busy, e.g. inside Stop's join) and stops a slow UI
from building a backlog of stale frames.
"""

import threading


class LatestOnly:
    def __init__(self):
        self._lock = threading.Lock()
        self._item = None

    def put(self, item) -> None:
        with self._lock:
            self._item = item

    def take(self):
        """Return the newest item and clear the slot, or None if empty."""
        with self._lock:
            item, self._item = self._item, None
            return item
