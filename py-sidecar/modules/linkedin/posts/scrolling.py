"""Scroll helpers for LinkedIn lazy-loaded activity feeds."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Union

from playwright.async_api import Page

if TYPE_CHECKING:
    from browser.page import ScrapedPage

PageLike = Union[Page, "ScrapedPage"]

# LinkedIn often scrolls a nested main/scaffold container, not window.
_SCROLL_DOWN_JS = """() => {
    const canScroll = (el) => {
        if (!el) return false;
        const style = getComputedStyle(el);
        const oy = style.overflowY;
        if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return false;
        return el.scrollHeight > el.clientHeight + 1;
    };
    const findScrollRoot = () => {
        const main = document.querySelector('main');
        if (canScroll(main)) return main;
        for (let el = main?.parentElement; el; el = el.parentElement) {
            if (canScroll(el)) return el;
        }
        return document.scrollingElement || document.documentElement;
    };
    const root = findScrollRoot();
    const step = Math.max(200, root.clientHeight * 0.85);
    root.scrollTop = Math.min(root.scrollTop + step, root.scrollHeight);

    const containers = document.querySelectorAll(
        'div.feed-shared-update-v2, div[data-urn*="activity"], li.profile-creator-shared-feed-update__container, div[data-urn*="urn:li:activity"]'
    );
    if (containers.length) {
        containers[containers.length - 1].scrollIntoView({ block: 'end', behavior: 'instant' });
    }
}"""

_COUNT_POSTS_JS = """() => {
    const seen = new Set();
    const containers = document.querySelectorAll(
        'div.feed-shared-update-v2, div[data-urn*="activity"], li.profile-creator-shared-feed-update__container, div[data-urn*="urn:li:activity"]'
    );
    for (const el of containers) {
        const urn = el.getAttribute('data-urn') || el.dataset?.urn || '';
        const link = el.querySelector('a[href*="/feed/update/"], a[href*="activity"]');
        const href = link ? link.getAttribute('href') || '' : '';
        const urnMatch = urn.match(/activity:(\\d+)/);
        const hrefMatch = href.match(/activity[:/](\\d+)/);
        const postId = urnMatch ? urnMatch[1] : hrefMatch ? hrefMatch[1] : '';
        if (postId) seen.add(postId);
    }
    return seen.size;
}"""


async def scroll_feed_down(page: PageLike, *, delay: float = 1.5) -> None:
    """Scroll the feed container down and nudge the last visible post into view."""
    await page.evaluate(_SCROLL_DOWN_JS)
    await asyncio.sleep(delay)


async def count_posts_in_dom(page: PageLike) -> int:
    return int(await page.evaluate(_COUNT_POSTS_JS))
