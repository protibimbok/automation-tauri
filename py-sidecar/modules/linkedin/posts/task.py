"""LinkedIn posts scraper, expressed against the simple task API.

The framework owns the browser, the per-input loop, crash recovery, and status
reporting (see :mod:`modules.tasks.runner`). This task focuses on LinkedIn
domain logic: navigate to a profile's activity feed, scroll, extract posts, run
the optional matcher, and :meth:`collect` each post. Anchor/ordinal bookkeeping
is preserved so paused/closed runs resume without re-emitting seen posts.
"""

from __future__ import annotations

from typing import Any

from browser.page import ScrapedPage
from browser.sessions.storage import looks_logged_in_for_platform
from modules.tasks.base import BaseTask
from modules.tasks.registry import register_task

from .extractors import EXPAND_TRUNCATED_POSTS_JS, EXTRACT_POSTS_JS, parse_posts
from .scrolling import count_posts_in_dom, scroll_feed_down
from .urls import profile_activity_url

TASK_KEY = "linkedin.posts_scraper"

_STAGNANT_ROUNDS_LIMIT = 8


def _optional_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        result = int(value)
        return result if result > 0 else None
    except (TypeError, ValueError):
        return None


def _profile_url(data: dict[str, Any]) -> str:
    return str(data.get("profile_url") or data.get("url") or "").strip()


class LinkedInPostsTask(BaseTask):
    def resume(self, checkpoint: dict[str, Any]) -> None:
        """Seed scrape state from the last checkpoint (empty on a fresh run)."""
        self._profile_url = checkpoint.get("profile_url") or _profile_url(self.input)
        self._top_post_id: str | None = checkpoint.get("initial_top_post_id")
        self._snapshot_ids: list[str] = list(checkpoint.get("initial_post_ids") or [])
        self._initial_snapshot_ids: set[str] = set(self._snapshot_ids)
        self._seen_ids: set[str] = set(self._seen_keys)
        self._ordinal_map: dict[str, int] = {}
        self._next_ordinal = max(int(checkpoint.get("resume_from_ordinal") or 0), 0) + 1
        # Match count is per-session for the post_count limit (matches old scraper).
        self._matched = 0
        self._done = False

    async def run(self, page: ScrapedPage) -> None:
        profile_url = self._profile_url
        if not profile_url:
            raise RuntimeError("missing profile_url")

        self._post_count = _optional_int(self.params.get("post_count"))
        self._start_from = _optional_int(self.params.get("start_from")) or 1
        self._matcher = (self.params.get("post_matcher") or "").strip() or None

        self._activity_url = profile_activity_url(profile_url)
        await page.visit(self._activity_url, wait_until="domcontentloaded")
        if await self.sleep(2.0):
            return

        if not await self._looks_logged_in(page):
            raise RuntimeError(f"session is not logged in for {profile_url}")

        await self._snapshot_anchor(page)

        stagnant_rounds = 0
        last_dom_count = 0

        while not self.stopped and not self._done:
            if await self.checkpoint(self._build_cursor()):
                break

            posts = await self._extract_visible_posts(page)
            await self._process_posts(page, self._eligible_posts(posts))
            if self.stopped or self._done:
                break

            dom_count = await count_posts_in_dom(page)
            self.ctx.progress(
                input_id=self._input.input_id if self._input else "",
                collected=len(self._seen_ids),
                matched=self._matched,
                dom_count=dom_count,
                url=page.url,
            )

            if dom_count <= last_dom_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                last_dom_count = dom_count
            if stagnant_rounds >= _STAGNANT_ROUNDS_LIMIT:
                break

            if await self.checkpoint(self._build_cursor()):
                break
            await scroll_feed_down(page, delay=0)
            await self.sleep(1.5)

        self.set_cursor(self._build_cursor())

    # -- cursor ------------------------------------------------------------

    def _build_cursor(self) -> dict[str, Any]:
        return {
            "profile_url": self._profile_url,
            "initial_top_post_id": self._top_post_id,
            "initial_post_ids": self._snapshot_ids,
            "resume_from_ordinal": max(self._next_ordinal - 1, 0),
            "collected": len(self._seen_ids),
            "matched": self._matched,
        }

    def _limit_reached(self) -> bool:
        return self._post_count is not None and self._matched >= self._post_count

    # -- login / extraction ------------------------------------------------

    async def _looks_logged_in(self, page: ScrapedPage) -> bool:
        cookies = await page.context.cookies()
        return looks_logged_in_for_platform(
            "linkedin",
            check_url=self._activity_url,
            final_url=page.url,
            cookies=cookies,
        )

    async def _extract_visible_posts(self, page: ScrapedPage) -> list[dict[str, Any]]:
        await page.evaluate(EXPAND_TRUNCATED_POSTS_JS)
        raw = await page.evaluate(EXTRACT_POSTS_JS)
        return parse_posts(raw)

    async def _run_matcher(self, page: ScrapedPage, post: dict[str, Any]) -> bool:
        if not self._matcher:
            return True
        try:
            result = await page.evaluate(
                """
                ([code, post]) => {
                  try {
                    const fn = new Function('post', code);
                    return Boolean(fn(post));
                  } catch (e) {
                    return false;
                  }
                }
                """,
                [self._matcher, post],
            )
            return bool(result)
        except Exception:
            return False

    # -- anchor / ordinal bookkeeping (preserved from the old scraper) ------

    async def _snapshot_anchor(self, page: ScrapedPage) -> list[str]:
        posts = await self._extract_visible_posts(page)
        ids = [p["post_id"] for p in posts if p.get("post_id")]
        if not self._top_post_id and ids:
            self._top_post_id = ids[0]

        if not self._initial_snapshot_ids and ids:
            self._snapshot_ids = ids
            self._initial_snapshot_ids = set(ids)
            for idx, pid in enumerate(ids, start=1):
                self._ordinal_map.setdefault(pid, idx)
            self._next_ordinal = max(self._ordinal_map.values(), default=0) + 1
            # Persist the anchor immediately so a later resume can continue.
            if self._input is not None:
                self.ctx.input_status(
                    self._input.input_id, "running", self._build_cursor()
                )
        elif self._snapshot_ids:
            for idx, pid in enumerate(self._snapshot_ids, start=1):
                self._ordinal_map.setdefault(pid, idx)
            self._next_ordinal = max(
                self._next_ordinal, max(self._ordinal_map.values(), default=0) + 1
            )
        return ids

    def _eligible_posts(self, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Posts to process: anchor onward in DOM, skipping new-at-top inserts."""
        if not posts:
            return []
        top_id = self._top_post_id
        if not top_id:
            return posts

        dom_ids = [p.get("post_id") for p in posts]
        try:
            top_idx = dom_ids.index(top_id)
        except ValueError:
            top_idx = 0

        eligible: list[dict[str, Any]] = []
        for idx, post in enumerate(posts):
            post_id = post.get("post_id")
            if not post_id:
                continue
            if idx < top_idx and (
                post_id not in self._initial_snapshot_ids
                and post_id not in self._ordinal_map
                and post_id not in self._seen_ids
            ):
                continue
            eligible.append(post)
        return eligible

    def _ordinal_for(self, post_id: str) -> int:
        existing = self._ordinal_map.get(post_id)
        if existing is not None:
            return existing
        ordinal = self._next_ordinal
        self._next_ordinal += 1
        self._ordinal_map[post_id] = ordinal
        return ordinal

    async def _process_posts(
        self, page: ScrapedPage, posts: list[dict[str, Any]]
    ) -> None:
        for post in posts:
            if self.stopped:
                break
            if await self.checkpoint(self._build_cursor()):
                break
            post_id = post.get("post_id")
            if not post_id or post_id in self._seen_ids:
                continue

            ordinal = self._ordinal_for(post_id)
            if ordinal < self._start_from:
                self._seen_ids.add(post_id)
                continue

            matched = await self._run_matcher(page, post)
            self._seen_ids.add(post_id)

            self.collect({**post, "matched": matched}, key=post_id, ordinal=ordinal)

            if matched:
                self._matched += 1
                if self._limit_reached():
                    self._done = True
                    break


register_task(TASK_KEY, LinkedInPostsTask)
