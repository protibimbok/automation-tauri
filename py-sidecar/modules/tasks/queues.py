"""Lightweight in-memory named FIFO queues for task authors.

Queues are a convenience for breadth-first / nested extraction: a task can
``enqueue`` work it discovers while scraping and ``drain`` it later in the same
run. They are in-memory only (no persistence) and never auto-processed — the
task drains them itself.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterator


class TaskQueues:
    """Named FIFO queues backed by ``collections.deque``."""

    def __init__(self) -> None:
        self._queues: dict[str, deque[Any]] = {}

    def enqueue(self, item: Any, key: str = "default") -> None:
        """Append ``item`` to the named queue (created on first use)."""
        self._queues.setdefault(key, deque()).append(item)

    def dequeue(self, key: str = "default") -> Any:
        """Pop and return the oldest item. Raises ``IndexError`` if empty."""
        queue = self._queues.get(key)
        if not queue:
            raise IndexError(f"queue '{key}' is empty")
        return queue.popleft()

    def has_queue(self, key: str = "default") -> bool:
        """True if the named queue exists and still has items."""
        return bool(self._queues.get(key))

    def size(self, key: str = "default") -> int:
        """Number of items currently in the named queue."""
        queue = self._queues.get(key)
        return len(queue) if queue else 0

    def drain(self, key: str = "default") -> Iterator[Any]:
        """Yield items FIFO until the queue is empty.

        Items enqueued onto the same queue *during* iteration are also yielded,
        which supports nested discovery (enqueue-while-draining).
        """
        queue = self._queues.get(key)
        if queue is None:
            return
        while queue:
            yield queue.popleft()
