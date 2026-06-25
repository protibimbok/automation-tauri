"""Task base classes and the per-run execution context."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from browser.control import RunControl

from .queues import TaskQueues

if TYPE_CHECKING:
    from browser.page import ScrapedPage

EmitFn = Callable[[str, dict[str, Any]], None]


@dataclass
class TaskInput:
    """A single input row for a run (distinct from run-level parameters)."""

    input_id: str
    ordinal: int
    data: dict[str, Any] = field(default_factory=dict)
    cursor: dict[str, Any] | None = None
    seen_keys: list[str] = field(default_factory=list)


class TaskContext:
    """Carries run identity + inputs and emits progress events to the host."""

    def __init__(
        self,
        run_id: str,
        task_key: str,
        params: dict[str, Any] | None,
        inputs: list[TaskInput],
        emit: EmitFn | None,
    ) -> None:
        self.run_id = run_id
        self.task_key = task_key
        self.params: dict[str, Any] = params or {}
        self.inputs = inputs
        self._emit = emit

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._emit is not None:
            self._emit(event, payload)

    def status(
        self,
        status: str,
        *,
        pause_info: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.emit(
            "task.status",
            {
                "run_id": self.run_id,
                "status": status,
                "pause_info": pause_info,
                "error": error,
            },
        )

    def item(
        self,
        input_id: str,
        item_key: str,
        ordinal: int,
        data: dict[str, Any],
    ) -> None:
        self.emit(
            "task.item",
            {
                "run_id": self.run_id,
                "input_id": input_id,
                "item_key": item_key,
                "ordinal": ordinal,
                "data": data,
            },
        )

    def input_status(
        self,
        input_id: str,
        status: str,
        cursor: dict[str, Any] | None = None,
    ) -> None:
        self.emit(
            "task.input_status",
            {
                "run_id": self.run_id,
                "input_id": input_id,
                "status": status,
                "cursor": cursor,
            },
        )

    def log(self, line: str, *, level: str = "info") -> None:
        self.emit(
            "task.log",
            {
                "run_id": self.run_id,
                "ts": time.time(),
                "level": level,
                "line": str(line),
            },
        )

    def progress(self, **metrics: Any) -> None:
        self.emit("task.progress", {"run_id": self.run_id, **metrics})


class BaseTask:
    """Base class for runnable tasks.

    Subclasses implement :meth:`run`, which the framework invokes **once per
    input row** with a ready :class:`~browser.page.ScrapedPage`. The framework
    owns the browser lifecycle, crash recovery, the per-input loop, and status
    reporting; the task focuses on navigation, extraction, and :meth:`collect`.
    """

    def __init__(self, ctx: TaskContext) -> None:
        self.ctx = ctx
        self.control = RunControl()
        self.queues = TaskQueues()
        # Bound by the runner before each run() call via _bind_input():
        self._input: TaskInput | None = None
        self._ordinal: int = 0
        self._seen_keys: set[str] = set()
        self._cursor: dict[str, Any] = {}

    async def run(self, page: "ScrapedPage") -> None:  # pragma: no cover
        raise NotImplementedError

    def resume(self, checkpoint: dict[str, Any]) -> Awaitable[None] | None:  # pragma: no cover
        """Restore per-input state before :meth:`run`.

        Called by the framework immediately before every ``run(page)`` with the
        data from the most recent :meth:`checkpoint` (an empty dict on a fresh
        run). Implement it to initialise/restore your starting state — using
        ``checkpoint.get(..., default)`` so the same code seeds both fresh and
        resumed runs. May be a coroutine if restoration needs to await.
        """
        raise NotImplementedError

    # -- per-input binding (called by the runner) --------------------------

    def _bind_input(self, inp: TaskInput) -> None:
        """Prepare per-input state before :meth:`run` (resume-aware)."""
        self._input = inp
        self._seen_keys = set(inp.seen_keys or [])
        self._cursor = dict(inp.cursor or {})
        self._ordinal = int(self._cursor.get("resume_from_ordinal") or 0)

    # -- params / current input -------------------------------------------

    @property
    def params(self) -> dict[str, Any]:
        """Run-level parameters."""
        return self.ctx.params

    @property
    def input(self) -> dict[str, Any]:
        """The current input row's data dict."""
        return self._input.data if self._input is not None else {}

    # -- result emission (maps onto ctx.item) ------------------------------

    def collect(
        self,
        data: dict[str, Any],
        key: Any | None = None,
        *,
        ordinal: int | None = None,
    ) -> None:
        """Emit one result record for the current input.

        ``key`` (the item key the host de-duplicates on) is resolved as:
        explicit ``key`` → ``data["_key"]`` → the auto-increment ordinal. A
        record whose key was already collected (e.g. on resume, seeded from the
        input's ``seen_keys``) is skipped silently. ``ordinal`` may be supplied
        for domain ordering schemes; otherwise it auto-increments per input.
        """
        if self._input is None:
            raise RuntimeError("collect() called outside of run()")

        item_key = key if key is not None else data.get("_key")
        if item_key is not None:
            item_key = str(item_key)
            if item_key in self._seen_keys:
                return

        if ordinal is not None:
            resolved = int(ordinal)
            self._ordinal = max(self._ordinal, resolved)
        else:
            self._ordinal += 1
            resolved = self._ordinal

        if item_key is None:
            item_key = str(resolved)

        self._seen_keys.add(item_key)
        self.ctx.item(self._input.input_id, item_key, resolved, dict(data))

    # -- named queues (delegate to self.queues) ----------------------------

    def enqueue(self, item: Any, key: str = "default") -> None:
        self.queues.enqueue(item, key)

    def dequeue(self, key: str = "default") -> Any:
        return self.queues.dequeue(key)

    def has_queue(self, key: str = "default") -> bool:
        return self.queues.has_queue(key)

    def drain(self, key: str = "default"):
        return self.queues.drain(key)

    # -- cooperative run control -------------------------------------------

    @property
    def stopped(self) -> bool:
        """True once a stop has been requested — check inside loops."""
        return self.control.stopped

    def set_cursor(self, cursor: dict[str, Any]) -> None:
        """Record the resume cursor for the current input."""
        self._cursor = dict(cursor)

    @property
    def cursor(self) -> dict[str, Any]:
        """The current input's resume cursor."""
        return self._cursor

    async def checkpoint(self, cursor: dict[str, Any] | None = None) -> bool:
        """Cooperative pause/stop point. Returns True if the task should exit.

        When ``cursor`` is given it is recorded (and reported as ``pause_info``
        on pause) so a paused run can resume from it. Call this inside scraping
        loops between units of work.
        """
        if cursor is not None:
            self._cursor = dict(cursor)
        if self.control.stopped:
            return True
        if self.control.is_paused:
            info = self._cursor or None
            input_id = self._input.input_id if self._input is not None else ""
            self.ctx.status("paused", pause_info=info)
            if self._input is not None:
                self.ctx.input_status(input_id, "paused", info)
            if await self.control.wait_if_paused():
                return True
            self.ctx.status("running")
            if self._input is not None:
                self.ctx.input_status(input_id, "running", info)
        return self.control.stopped

    async def sleep(self, seconds: float) -> bool:
        """Pause-aware sleep. Returns True if stopped during the wait."""
        return await self.control.pause_aware_sleep(seconds)
