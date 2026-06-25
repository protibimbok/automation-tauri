"""A thin convenience wrapper over a Playwright Page.

Task authors receive a :class:`ScrapedPage` rather than a raw Playwright page.
It adds the high-level :meth:`visit` helper and transparently delegates every
other attribute to the underlying page (so ``.evaluate``, ``.url``, ``.goto``,
``.context``, ``.wait_for_selector`` all still work). Awaitable operations are
wrapped with crash recovery: if the browser dies mid-operation the framework
relaunches Chrome, re-navigates to the last visited URL, and retries once — so
individual tasks never reimplement the retry dance.
"""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from playwright.async_api import Page

from .errors import is_recoverable_browser_error

_LOAD_STATES = {"load", "domcontentloaded", "networkidle", "commit"}

RecoverFn = Callable[[], Awaitable[None]]


class ScrapedPage:
    """Wraps a Playwright :class:`Page`; the framework owns the real page."""

    def __init__(self, page: Page, *, recover: RecoverFn | None = None) -> None:
        object.__setattr__(self, "_page", page)
        object.__setattr__(self, "_recover", recover)
        object.__setattr__(self, "_last_url", "")

    @property
    def raw(self) -> Page:
        """The underlying Playwright page (escape hatch for advanced use)."""
        return self._page

    @property
    def last_url(self) -> str:
        """The URL passed to the most recent :meth:`visit`."""
        return self._last_url

    def _set_page(self, page: Page) -> None:
        """Swap the underlying page (used by the runner after a relaunch)."""
        object.__setattr__(self, "_page", page)

    def _set_recover(self, recover: RecoverFn | None) -> None:
        object.__setattr__(self, "_recover", recover)

    async def visit(
        self,
        url: str,
        *,
        wait_for: str | None = None,
        wait_until: str = "domcontentloaded",
        timeout: int = 90_000,
    ) -> None:
        """Navigate to ``url`` then optionally wait for readiness.

        ``wait_until`` is the navigation signal handed to ``goto``. ``wait_for``,
        when given, is either a load state (one of ``load``/``domcontentloaded``/
        ``networkidle``/``commit``) awaited via ``wait_for_load_state``, or any
        other string treated as a CSS selector awaited via ``wait_for_selector``.
        """
        object.__setattr__(self, "_last_url", url)
        await self._call("goto", url, wait_until=wait_until, timeout=timeout)
        if wait_for is None:
            return
        if wait_for in _LOAD_STATES:
            await self._call("wait_for_load_state", wait_for)
        else:
            await self._call("wait_for_selector", wait_for, timeout=timeout)

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a coroutine method on the page, retrying once on a crash."""
        try:
            return await getattr(self._page, method)(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - reclassified below
            if self._recover is None or not is_recoverable_browser_error(exc):
                raise
            await self._recover()
            return await getattr(self._page, method)(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires for names not set on the instance/class, so the
        # wrapper's own attributes (_page, visit, ...) never reach here.
        attr = getattr(self._page, name)
        if inspect.iscoroutinefunction(attr):

            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self._call(name, *args, **kwargs)

            return wrapper
        return attr
