"""Single Google Chrome browser instance with unique run id and run control."""

from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import Browser, BrowserContext, Page, Playwright

from .chrome_cdp import ChromeCdpSession, launch_chrome_cdp, shutdown_chrome_cdp
from .control import RunControl
from .install import ensure_chrome
from .pages import close_page

EmitFn = Callable[[str, dict[str, Any]], None]


def _browser_profiles_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "tauri-py" / "browser-profiles"
    return Path.home() / ".tauri-py" / "browser-profiles"


def browser_run_profile_path(run_id: str) -> Path:
    return _browser_profiles_root() / run_id


@dataclass(frozen=True)
class BrowserRunInfo:
    run_id: str
    headless: bool
    url: str
    running: bool
    paused: bool = False
    crashed: bool = False


class BrowserInstance:
    """Owns one Chrome lifecycle keyed by a unique run id."""

    def __init__(
        self,
        *,
        headless: bool = True,
        emit: EmitFn | None = None,
    ) -> None:
        self.run_id = str(uuid.uuid4())
        self.control = RunControl()
        self._emit = emit
        self._stack = AsyncExitStack()
        self._playwright: Playwright | None = None
        self._headless = headless
        self._crashed = False
        self._closing = False
        self._started = False
        self._cdp: ChromeCdpSession | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    @property
    def headless(self) -> bool:
        return self._headless

    def _is_alive(self) -> bool:
        if self._cdp is None or self.browser is None:
            return False
        try:
            if not self.browser.is_connected():
                return False
            if self.page is None or self.page.is_closed():
                return False
            if self._cdp.process.poll() is not None:
                return False
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        return self._started and self._is_alive()

    def info(self) -> BrowserRunInfo:
        url = ""
        if self.is_running and self.page is not None:
            url = self.page.url
        return BrowserRunInfo(
            run_id=self.run_id,
            headless=self.headless,
            url=url,
            running=self.is_running,
            paused=self.control.is_paused,
            crashed=self._crashed,
        )

    def _on_page_close(self, _: Page) -> None:
        self._schedule_external_close(crashed=False)

    def _on_browser_disconnected(self, _: Browser) -> None:
        self._schedule_external_close(crashed=True)

    def _schedule_external_close(self, *, crashed: bool) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._handle_external_close(crashed=crashed))

    async def _handle_external_close(self, *, crashed: bool) -> None:
        if self._closing:
            return

        self._closing = True
        try:
            headless = self.headless
            run_id = self.run_id
            self._crashed = crashed
            await self._shutdown()
            await self._stack.aclose()
            self._stack = AsyncExitStack()
            self._playwright = None
            self._started = False
            self._emit_closed(
                run_id=run_id,
                headless=headless,
                crashed=crashed,
            )
        finally:
            self._closing = False

    def _emit_closed(self, *, run_id: str, headless: bool, crashed: bool) -> None:
        if self._emit is None:
            return
        self._emit(
            "browser.closed",
            {
                "ok": True,
                "run_id": run_id,
                "running": False,
                "headless": headless,
                "url": "",
                "crashed": crashed,
                "paused": False,
            },
        )

    def _emit_updated(self) -> None:
        if self._emit is None:
            return
        info = self.info()
        self._emit(
            "browser.updated",
            {
                "ok": True,
                "run_id": info.run_id,
                "running": info.running,
                "headless": info.headless,
                "url": info.url,
                "paused": info.paused,
                "crashed": info.crashed,
            },
        )

    def _on_framenavigated(self, frame: Any) -> None:
        if self.page is not None and frame == self.page.main_frame:
            self._emit_updated()

    async def refresh(self) -> bool:
        if not self._started or self.browser is None:
            return self._crashed

        if self._is_alive():
            self._crashed = False
            return False

        crashed = True
        try:
            crashed = not self.browser.is_connected()
        except Exception:
            crashed = True

        await self._handle_external_close(crashed=crashed)
        return crashed

    async def start(self) -> BrowserRunInfo:
        if self.is_running:
            raise RuntimeError(f"browser '{self.run_id}' is already running")

        await ensure_chrome()
        self._crashed = False

        from playwright.async_api import async_playwright

        self._playwright = await self._stack.enter_async_context(async_playwright())
        await self._launch()
        self._started = True
        assert self.page is not None
        return self.info()

    async def recover(self) -> BrowserRunInfo:
        await self.refresh()
        if self._playwright is None:
            raise RuntimeError(f"browser '{self.run_id}' is not running")

        await self._shutdown()
        await asyncio.sleep(1.0)
        await self._launch()
        self._started = True
        assert self.page is not None
        return self.info()

    async def stop(self) -> BrowserRunInfo:
        await self.refresh()
        if not self._started and self.browser is None:
            return BrowserRunInfo(
                run_id=self.run_id,
                headless=self.headless,
                url="",
                running=False,
                paused=False,
                crashed=self._crashed,
            )

        self.control.stop()
        self._closing = True
        try:
            await self._shutdown()
            await self._stack.aclose()
            self._stack = AsyncExitStack()
            self._playwright = None
            self._started = False
            self._crashed = False
            return BrowserRunInfo(
                run_id=self.run_id,
                headless=self.headless,
                url="",
                running=False,
                paused=False,
                crashed=False,
            )
        finally:
            self._closing = False

    async def _launch(self) -> None:
        assert self._playwright is not None
        profile_dir = browser_run_profile_path(self.run_id)
        self._cdp = await launch_chrome_cdp(
            self._playwright,
            profile_dir=profile_dir,
            headless=self._headless,
            fresh=False,
        )
        self.browser = self._cdp.browser
        self.context = self._cdp.context
        self.page = self._cdp.page
        self.browser.on("disconnected", self._on_browser_disconnected)
        self.page.on("close", self._on_page_close)
        self.page.on("framenavigated", self._on_framenavigated)

    async def _shutdown(self) -> None:
        if self.page is not None:
            try:
                self.page.remove_listener("framenavigated", self._on_framenavigated)
            except Exception:
                pass
            try:
                self.page.remove_listener("close", self._on_page_close)
            except Exception:
                pass
            await close_page(self.page)
            self.page = None
        if self.browser is not None:
            try:
                self.browser.remove_listener(
                    "disconnected", self._on_browser_disconnected
                )
            except Exception:
                pass
        self.context = None
        self.browser = None
        await shutdown_chrome_cdp(self._cdp)
        self._cdp = None
