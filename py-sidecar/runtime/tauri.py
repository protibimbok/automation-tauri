from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .bus_message import BusMessage


class _PendingRequests:
    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._counter = 0

    def insert(self) -> tuple[str, asyncio.Future[Any]]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        request_id = str(self._counter)
        self._counter += 1
        self._pending[request_id] = future
        return request_id, future

    def respond(self, request_id: str, value: Any) -> None:
        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            future.set_result(value)

    def fail(self, request_id: str, error: str) -> None:
        future = self._pending.pop(request_id, None)
        if future is not None and not future.done():
            future.set_exception(RuntimeError(error))


_pending_requests = _PendingRequests()


class Tauri:
    _send: Callable[[str], None] | None = None

    @classmethod
    def init(cls, send: Callable[[str], None]) -> None:
        cls._send = send

    @classmethod
    def _emit(cls, message: BusMessage) -> None:
        if cls._send is None:
            raise RuntimeError("Tauri is not initialized")
        cls._send(message.to_json())

    @classmethod
    def dispatch(cls, event: str, payload: Any) -> None:
        cls._emit(BusMessage.event(event, payload))

    @classmethod
    async def request(cls, route: str, payload: Any, timeout: float = 10.0) -> Any:
        request_id, future = _pending_requests.insert()
        cls._emit(BusMessage.request(request_id, route, payload))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            _pending_requests.fail(request_id, f"[PY] #{request_id} timeout")
            raise TimeoutError(f"[PY] #{request_id} timeout") from exc
