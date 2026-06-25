from __future__ import annotations

import asyncio
import json
import sys
import threading
from collections.abc import Callable
from typing import Any

from .app import Daemon
from .bus_message import BusMessage
from .error_log import error_log
from .tauri import Tauri, _pending_requests


def _force_utf8_stdio() -> None:
    for stream, kwargs in (
        (sys.stdout, {"encoding": "utf-8", "newline": "\n"}),
        (sys.stdin, {"encoding": "utf-8"}),
        (sys.stderr, {"encoding": "utf-8"}),
    ):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(**kwargs)
            except (ValueError, OSError):
                pass


class _Runner:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: set[asyncio.Task[None]] = set()
        self._write_lock = threading.Lock()

    def _send_line(self, line: str) -> None:
        with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def _track(self, task: asyncio.Task[None]) -> None:
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _run_handler(self, handler: Callable[..., Any], payload: Any) -> Any:
        if asyncio.iscoroutinefunction(handler):
            return await handler(payload)
        return handler(payload)

    def _respond(self, request_id: str, payload: Any) -> None:
        _pending_requests.respond(request_id, payload)

    def _handle_line(self, line: str) -> None:
        assert self._loop is not None

        line = line.strip()
        if not line:
            return

        try:
            msg = BusMessage.from_json(line)
        except (json.JSONDecodeError, KeyError) as exc:
            error_log(f"[PY] invalid json: {line!r} ({exc})")
            return

        if msg.kind == "event":
            handlers = Daemon._event_handlers.get(msg.route, [])
            if not handlers:
                error_log(f"[PY] no handler for event: {msg.route}")
                return
            for handler in handlers:
                task = self._loop.create_task(self._run_handler(handler, msg.payload))
                self._track(task)
            return

        if msg.kind == "request":
            handler = Daemon._route_handlers.get(msg.route)
            if handler is None:
                error_log(f"[PY] no handler for request: {msg.route}")
                return

            async def handle_request() -> None:
                try:
                    result = await self._run_handler(handler, msg.payload)
                    self._send_line(msg.to_response(result).to_json())
                except Exception as exc:
                    error_log(f"[PY] request handler error: {exc}")
                    self._send_line(msg.to_response({"error": str(exc)}).to_json())

            self._track(self._loop.create_task(handle_request()))
            return

        if msg.kind == "response":
            if not msg.id:
                error_log("[PY] response message has no id")
                return
            self._respond(msg.id, msg.payload)
            return

        error_log(f"[PY] unknown message kind: {msg.kind}")

    def _read_stdin(self, in_queue: asyncio.Queue[str | None]) -> None:
        assert self._loop is not None
        try:
            for line in sys.stdin:
                self._loop.call_soon_threadsafe(in_queue.put_nowait, line)
        finally:
            self._loop.call_soon_threadsafe(in_queue.put_nowait, None)

    async def _run(self) -> None:
        self._loop = asyncio.get_running_loop()
        in_queue: asyncio.Queue[str | None] = asyncio.Queue()
        threading.Thread(target=self._read_stdin, args=(in_queue,), daemon=True).start()
        # Emit only after the stdin reader is running so early install.status
        # requests are not dropped before the loop can handle them.
        await asyncio.sleep(0)
        Tauri.dispatch("sidecar_ready", {"status": "ok"})

        while True:
            line = await in_queue.get()
            if line is None:
                break
            self._handle_line(line)

        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)


def run() -> None:
    _force_utf8_stdio()
    runner = _Runner()
    Tauri.init(runner._send_line)
    asyncio.run(runner._run())
