"""Drives a task: owns one Chrome lifecycle and calls run(page) per input.

The runner centralises everything tasks used to repeat by hand — launching and
tearing down Chrome (from the run's ``session_dir`` / ``headless`` params),
recovering from browser crashes, iterating the input rows, and reporting
per-input status. A task just implements :meth:`BaseTask.run`.
"""

from __future__ import annotations

import asyncio
import inspect
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from browser.chrome_cdp import (
    ChromeCdpSession,
    chrome_profile_path,
    launch_chrome_cdp,
    shutdown_chrome_cdp,
)
from browser.install import ensure_chrome
from browser.page import ScrapedPage

from .base import BaseTask, TaskContext, TaskInput

_RECOVER_SETTLE_SEC = 1.0


class TaskRunner:
    """Owns the browser for one run and invokes ``task.run(page)`` per input."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._playwright: Any = None
        self._cdp: ChromeCdpSession | None = None
        self._page: ScrapedPage | None = None
        self._headless = True
        self._profile_dir: Path | None = None

    async def run(self, task: BaseTask, ctx: TaskContext) -> None:
        params = ctx.params
        session_dir = str(params.get("session_dir") or "").strip()
        if not session_dir:
            raise RuntimeError("a session is required — select one before starting")
        self._headless = bool(params.get("headless", True))
        self._profile_dir = chrome_profile_path(Path(session_dir))

        await ensure_chrome()
        from playwright.async_api import async_playwright

        playwright = await self._stack.enter_async_context(async_playwright())
        self._playwright = playwright
        await self._launch()
        assert self._cdp is not None
        page = ScrapedPage(self._cdp.page, recover=self._recover)
        self._page = page

        inputs = ctx.inputs or [TaskInput(input_id="_run", ordinal=0)]
        try:
            for inp in inputs:
                if task.stopped:
                    break
                task._bind_input(inp)
                ctx.input_status(inp.input_id, "running", inp.cursor or None)
                try:
                    restored = task.resume(inp.cursor or {})
                    if inspect.isawaitable(restored):
                        await restored
                    await task.run(page)
                except Exception as exc:  # noqa: BLE001 - per-input failure
                    ctx.log(f"Input failed: {exc}", level="error")
                    ctx.input_status(inp.input_id, "failed", task.cursor or None)
                    continue
                if task.stopped:
                    ctx.input_status(inp.input_id, "stopped", task.cursor or None)
                    break
                ctx.input_status(inp.input_id, "done", task.cursor or None)
        finally:
            await self._shutdown()
            await self._stack.aclose()
            self._stack = AsyncExitStack()

    async def _launch(self) -> ChromeCdpSession:
        assert self._profile_dir is not None
        self._cdp = await launch_chrome_cdp(
            self._playwright,
            profile_dir=self._profile_dir,
            headless=self._headless,
            fresh=False,
        )
        return self._cdp

    async def _recover(self) -> None:
        """Relaunch Chrome and re-navigate to the last visited URL."""
        last_url = self._page.last_url if self._page is not None else ""
        await shutdown_chrome_cdp(self._cdp)
        self._cdp = None
        await asyncio.sleep(_RECOVER_SETTLE_SEC)
        self._cdp = await self._launch()
        assert self._page is not None
        self._page._set_page(self._cdp.page)
        if last_url:
            await self._cdp.page.goto(
                last_url, wait_until="domcontentloaded", timeout=90_000
            )
            await asyncio.sleep(2.0)

    async def _shutdown(self) -> None:
        await shutdown_chrome_cdp(self._cdp)
        self._cdp = None
        self._page = None
