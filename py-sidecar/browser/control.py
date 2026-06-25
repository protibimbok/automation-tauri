"""Pause / resume / stop control for long-running browser automation."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class RunControl:
    """Cooperative run control checked before each scrape iteration."""

    def __init__(self) -> None:
        self._paused = asyncio.Event()
        self._paused.set()
        self._stop = False

    @property
    def stopped(self) -> bool:
        return self._stop

    @property
    def is_paused(self) -> bool:
        return not self._paused.is_set()

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()

    def stop(self) -> None:
        self._stop = True
        self._paused.set()

    async def wait_if_paused(self) -> bool:
        """Block while paused. Returns True when the run should exit."""
        await self._paused.wait()
        return self._stop

    async def pause_aware_sleep(self, seconds: float) -> bool:
        """Sleep in short slices so pause/stop stay responsive."""
        remaining = seconds
        while remaining > 0:
            if self._stop:
                return True
            if not self._paused.is_set():
                await self._paused.wait()
                if self._stop:
                    return True
            step = min(remaining, 0.1)
            await asyncio.sleep(step)
            remaining -= step
        return self._stop


class ControlledIterator(Generic[T]):
    """Async iterator that checks pause/resume/stop before each item."""

    def __init__(self, items: Iterable[T] | Iterator[T], control: RunControl) -> None:
        self._iter = iter(items)
        self._control = control

    def __aiter__(self) -> ControlledIterator[T]:
        return self

    async def __anext__(self) -> T:
        if await self._control.wait_if_paused():
            raise StopAsyncIteration
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


async def controlled_iterate(
    control: RunControl,
    items: Iterable[T],
) -> AsyncIterator[T]:
    """Yield items one at a time, honouring pause/resume/stop between steps."""
    async for item in ControlledIterator(items, control):
        yield item
