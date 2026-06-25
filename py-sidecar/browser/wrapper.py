"""Scraping helpers with crash recovery and run-control integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

from .control import RunControl, controlled_iterate
from .errors import is_recoverable_browser_error
from .instance import BrowserInstance

T = TypeVar("T")
R = TypeVar("R")

_RECOVER_SETTLE_SEC = 1.0


async def with_page_retry(
    instance: BrowserInstance,
    fn: Callable[[], Awaitable[R]],
    *,
    recover_url: str | None = None,
) -> R:
    """Run *fn* on the instance page; recover and retry once on browser errors."""
    assert instance.page is not None
    try:
        return await fn()
    except Exception as exc:
        if not is_recoverable_browser_error(exc):
            raise
        await recover_instance(instance, url=recover_url)
        return await fn()


async def recover_instance(
    instance: BrowserInstance,
    *,
    url: str | None = None,
) -> None:
    """Relaunch the browser and optionally navigate back to *url*."""
    await instance.recover()
    if url and instance.page is not None:
        await instance.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        await asyncio.sleep(_RECOVER_SETTLE_SEC)


async def run_controlled_steps(
    control: RunControl,
    items: Iterable[T],
    step: Callable[[T], Awaitable[Any]],
) -> bool:
    """
    Iterate *items*, calling *step* for each after checking pause/stop.
    Returns True when stopped early.
    """
    async for item in controlled_iterate(control, items):
        if control.stopped:
            return True
        await step(item)
    return control.stopped


async def with_instance_retry(
    instance: BrowserInstance,
    fn: Callable[[BrowserInstance], Awaitable[R]],
    *,
    recover_url: str | None = None,
    max_attempts: int = 2,
) -> R:
    """Run *fn* with full instance recovery between attempts."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn(instance)
        except Exception as exc:
            last_exc = exc
            if not is_recoverable_browser_error(exc) or attempt + 1 >= max_attempts:
                raise
            await recover_instance(instance, url=recover_url)
    assert last_exc is not None
    raise last_exc
