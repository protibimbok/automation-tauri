"""Page helpers."""

from __future__ import annotations

from playwright.async_api import BrowserContext, Page


async def close_page(page: Page) -> None:
    try:
        if not page.is_closed():
            await page.close()
    except Exception:
        pass


async def open_page(context: BrowserContext) -> Page:
    return await context.new_page()
