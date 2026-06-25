"""Per-session Chrome lifecycle with a persistent profile controlled over CDP."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from playwright.async_api import Browser, BrowserContext, Page, Playwright

from ..chrome_cdp import (
    ChromeCdpSession,
    chrome_profile_path,
    clear_profile_locks,
    launch_chrome_cdp,
    shutdown_chrome_cdp,
)
from ..install import ensure_chrome
from ..pages import close_page
from .default import is_default_chrome_session
from .storage import (
    looks_logged_in_for_platform,
    save_storage_state,
    storage_path,
)
from .sync import sync_system_chrome_profile

EmitFn = Callable[[str, dict[str, Any]], None]


def _info_payload(info: SessionRunInfo) -> dict[str, Any]:
    return {
        "ok": True,
        "session_id": info.session_id,
        "run_id": info.run_id,
        "running": info.running,
        "headless": info.headless,
        "url": info.url,
        "crashed": info.crashed,
    }


@dataclass(frozen=True)
class SessionRunInfo:
    session_id: str
    run_id: str
    headless: bool
    url: str
    running: bool
    crashed: bool = False


class SessionRunner:
    def __init__(
        self,
        session_id: str,
        session_dir: Path | None,
        *,
        emit: EmitFn | None = None,
    ) -> None:
        self.session_id = session_id
        self.session_dir = session_dir
        if session_dir is not None:
            session_dir.mkdir(parents=True, exist_ok=True)
        self._emit = emit
        self._stack = AsyncExitStack()
        self._playwright: Playwright | None = None
        self._headless = False
        self._run_id: str | None = None
        self._crashed = False
        self._closing = False
        self._cdp: ChromeCdpSession | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def _launch_profile_dir(self) -> Path:
        assert self.session_dir is not None
        return chrome_profile_path(self.session_dir)

    def _is_alive(self) -> bool:
        if self._cdp is None or self.browser is None or self._run_id is None:
            return False
        try:
            if not self.browser.is_connected():
                return False
            if self._cdp.process.poll() is not None:
                return False
            if self.context is not None:
                open_pages = [page for page in self.context.pages if not page.is_closed()]
                if not open_pages:
                    return False
                if self.page is None or self.page.is_closed():
                    self.page = open_pages[0]
            elif self.page is None or self.page.is_closed():
                return False
            return True
        except Exception:
            return False

    @property
    def is_running(self) -> bool:
        return self._is_alive()

    def info(self) -> SessionRunInfo:
        url = ""
        if self.is_running and self.page is not None:
            url = self.page.url
        return SessionRunInfo(
            session_id=self.session_id,
            run_id=self._run_id or "",
            headless=self._headless,
            url=url,
            running=self.is_running,
            crashed=self._crashed,
        )

    def _should_emit_status(self) -> bool:
        return self._emit is not None and not self._headless

    def _emit_updated(self) -> None:
        if not self._should_emit_status():
            return
        self._emit("session.updated", _info_payload(self.info()))

    def _on_framenavigated(self, frame: Any) -> None:
        if self.page is not None and frame == self.page.main_frame:
            self._emit_updated()

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

    async def _save_storage(self) -> None:
        if self.context is None or self.session_dir is None:
            return
        await save_storage_state(self.context, self.session_dir)

    async def _handle_external_close(self, *, crashed: bool) -> None:
        if self._closing or self._run_id is None:
            return

        self._closing = True
        try:
            run_id = self._run_id
            headless = self._headless
            self._crashed = crashed
            await self._save_storage()
            await self._shutdown()
            await self._stack.aclose()
            self._stack = AsyncExitStack()
            self._playwright = None
            self._run_id = None
            if self._emit is not None:
                self._emit(
                    "session.closed",
                    {
                        "ok": True,
                        "session_id": self.session_id,
                        "run_id": run_id,
                        "running": False,
                        "headless": headless,
                        "url": "",
                        "crashed": crashed,
                    },
                )
        finally:
            self._closing = False

    async def launch(
        self, *, headless: bool = False, fresh: bool = False, start_url: str | None = None
    ) -> SessionRunInfo:
        if self.is_running:
            raise RuntimeError("session browser is already running")

        await ensure_chrome()
        self._headless = headless
        self._run_id = str(uuid.uuid4())
        self._crashed = False

        if fresh:
            await self._reset_session_data()

        from playwright.async_api import async_playwright

        self._playwright = await self._stack.enter_async_context(async_playwright())
        await self._launch()
        assert self.page is not None and self._run_id is not None

        if start_url:
            await self.page.goto(
                start_url, wait_until="domcontentloaded", timeout=60_000
            )

        return SessionRunInfo(
            session_id=self.session_id,
            run_id=self._run_id,
            headless=headless,
            url=self.page.url,
            running=True,
        )

    async def stop(self, *, run_id: str | None = None) -> SessionRunInfo | None:
        if not self.is_running and self._run_id is None:
            return None

        if run_id is not None and self._run_id != run_id:
            raise RuntimeError(f"unknown session run '{run_id}'")

        self._closing = True
        try:
            stopped_id = self._run_id or ""
            headless = self._headless
            await self._save_storage()
            await self._shutdown()
            await self._stack.aclose()
            self._stack = AsyncExitStack()
            self._playwright = None
            self._run_id = None
            self._crashed = False
            if self._emit is not None and stopped_id and not headless:
                self._emit(
                    "session.updated",
                    {
                        "ok": True,
                        "session_id": self.session_id,
                        "run_id": stopped_id,
                        "running": False,
                        "headless": headless,
                        "url": "",
                        "crashed": False,
                    },
                )
            return SessionRunInfo(
                session_id=self.session_id,
                run_id=stopped_id,
                headless=headless,
                url="",
                running=False,
            )
        finally:
            self._closing = False

    async def check(self, *, check_url: str, platform: str) -> dict[str, Any]:
        info = await self.launch(headless=True, fresh=False)
        assert self.page is not None
        try:
            cookies = await self.context.cookies() if self.context else []
            await self.page.goto(check_url, wait_until="domcontentloaded", timeout=60_000)
            await asyncio.sleep(1.0)
            final_url = self.page.url
            cookies = await self.context.cookies() if self.context else cookies
            logged_in = looks_logged_in_for_platform(
                platform,
                check_url=check_url,
                final_url=final_url,
                cookies=cookies,
            )
            return {
                "ok": True,
                "session_id": self.session_id,
                "run_id": info.run_id,
                "url": final_url,
                "logged_in": logged_in,
                "cookie_count": len(cookies),
            }
        finally:
            await self.stop(run_id=info.run_id)

    async def _reset_session_data(self) -> None:
        if self.session_dir is None:
            return
        state_file = storage_path(self.session_dir)
        if state_file.is_file():
            state_file.unlink(missing_ok=True)
        profile_dir = chrome_profile_path(self.session_dir)
        if profile_dir.exists():
            shutil.rmtree(profile_dir, ignore_errors=True)

    async def _launch(self) -> None:
        assert self._playwright is not None
        self._cdp = await launch_chrome_cdp(
            self._playwright,
            profile_dir=self._launch_profile_dir(),
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


class SessionManager:
    def __init__(self) -> None:
        self._runners: dict[str, SessionRunner] = {}
        self._emit: EmitFn | None = None

    def set_emit(self, emit: EmitFn) -> None:
        self._emit = emit

    def _emit_updated(self, info: SessionRunInfo) -> None:
        if self._emit is None or info.headless:
            return
        self._emit("session.updated", _info_payload(info))

    def _runner(self, session_id: str, session_dir: Path | None) -> SessionRunner:
        runner = self._runners.get(session_id)
        if runner is None:
            runner = SessionRunner(session_id, session_dir, emit=self._emit)
            self._runners[session_id] = runner
        return runner

    async def launch(
        self,
        *,
        session_id: str,
        session_dir: Path | None,
        headless: bool = False,
        fresh: bool = False,
        start_url: str | None = None,
    ) -> SessionRunInfo:
        runner = self._runner(session_id, session_dir)
        info = await runner.launch(
            headless=headless, fresh=fresh, start_url=start_url
        )
        if info.running:
            self._emit_updated(info)
        return info

    async def stop(
        self,
        *,
        session_id: str,
        session_dir: Path | None,
        run_id: str | None = None,
    ) -> SessionRunInfo | None:
        runner = self._runner(session_id, session_dir)
        info = await runner.stop(run_id=run_id)
        if not runner.is_running:
            self._runners.pop(session_id, None)
        return info

    async def check(
        self,
        *,
        session_id: str,
        session_dir: Path | None,
        check_url: str,
        platform: str,
    ) -> dict[str, Any]:
        runner = self._runner(session_id, session_dir)
        try:
            return await runner.check(check_url=check_url, platform=platform)
        finally:
            if not runner.is_running:
                self._runners.pop(session_id, None)

    async def sync_system_profile(
        self,
        *,
        session_id: str,
        session_dir: Path,
    ) -> dict[str, Any]:
        if not is_default_chrome_session(session_id):
            raise RuntimeError("only Default Chrome can sync from the system profile")

        runner = self._runner(session_id, session_dir)
        if runner.is_running:
            raise RuntimeError(
                "close the Default Chrome browser before syncing from system Chrome"
            )

        profile_dir = chrome_profile_path(session_dir)
        clear_profile_locks(profile_dir, require_idle=False)
        sync_result = sync_system_chrome_profile(profile_dir)

        info = await runner.launch(headless=True, fresh=False)
        cookie_count = 0
        try:
            if runner.context is not None:
                cookies = await runner.context.cookies()
                cookie_count = len(cookies)
        finally:
            await runner.stop(run_id=info.run_id)
            if not runner.is_running:
                self._runners.pop(session_id, None)

        return {
            "ok": True,
            "session_id": session_id,
            "files_copied": sync_result.files_copied,
            "cookie_count": cookie_count,
        }

    async def _reconcile_stale_runners(self) -> None:
        for sid, runner in list(self._runners.items()):
            if runner._run_id is None:
                self._runners.pop(sid, None)
                continue
            if runner.is_running:
                continue
            crashed = (
                runner._cdp is not None and runner._cdp.process.poll() is not None
            )
            await runner._handle_external_close(crashed=crashed)

    async def status(
        self, *, session_id: str | None = None
    ) -> SessionRunInfo | list[SessionRunInfo]:
        await self._reconcile_stale_runners()

        if session_id is not None:
            runner = self._runners.get(session_id)
            if runner is not None and runner.is_running and runner._run_id is not None:
                url = runner.page.url if runner.page is not None else ""
                return SessionRunInfo(
                    session_id=session_id,
                    run_id=runner._run_id,
                    headless=runner._headless,
                    url=url,
                    running=True,
                )
            return SessionRunInfo(
                session_id=session_id,
                run_id="",
                headless=False,
                url="",
                running=False,
            )

        results: list[SessionRunInfo] = []
        for sid, runner in list(self._runners.items()):
            if not runner.is_running or runner._run_id is None:
                continue
            url = runner.page.url if runner.page is not None else ""
            results.append(
                SessionRunInfo(
                    session_id=sid,
                    run_id=runner._run_id,
                    headless=runner._headless,
                    url=url,
                    running=True,
                )
            )
        return results


_manager = SessionManager()


def get_session_manager() -> SessionManager:
    return _manager
