from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

EventHandler = Callable[[Any], Awaitable[None] | None]
RouteHandler = Callable[[Any], Awaitable[Any] | Any]


class Daemon:
    """Registers inbound events and request routes for the sidecar."""

    _event_handlers: ClassVar[dict[str, list[EventHandler]]] = {}
    _route_handlers: ClassVar[dict[str, RouteHandler]] = {}

    @staticmethod
    def on(event: str, handler: EventHandler) -> None:
        Daemon._event_handlers.setdefault(event, []).append(handler)

    @staticmethod
    def route(path: str, handler: RouteHandler) -> None:
        if path in Daemon._route_handlers:
            raise ValueError(f"route handler for {path} already exists")
        Daemon._route_handlers[path] = handler
