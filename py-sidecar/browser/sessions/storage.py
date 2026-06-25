"""Persist Playwright storage state (cookies + local storage) per session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import BrowserContext

from ..chrome_cdp import chrome_profile_path

STORAGE_FILENAME = "storage_state.json"

PLATFORM_AUTH_COOKIES: dict[str, frozenset[str]] = {
    "linkedin": frozenset({"li_at"}),
    "facebook": frozenset({"c_user"}),
    "twitter": frozenset({"auth_token"}),
}


def storage_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / STORAGE_FILENAME


def has_storage(session_dir: str | Path) -> bool:
    path = storage_path(session_dir)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cookies = payload.get("cookies")
            if isinstance(cookies, list) and cookies:
                return True
        except (OSError, json.JSONDecodeError):
            pass

    profile = chrome_profile_path(session_dir)
    return profile.is_dir() and any(profile.iterdir())


def _existing_origins(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    origins = payload.get("origins")
    return origins if isinstance(origins, list) else []


async def save_storage_state(context: BrowserContext, session_dir: str | Path) -> None:
    """Write cookies (and preserved localStorage) to storage_state.json."""
    path = storage_path(session_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        await context.storage_state(path=str(path))
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("cookies"):
                return
    except Exception:
        pass

    cookies = await context.cookies()
    state = {"cookies": cookies, "origins": _existing_origins(path)}
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def has_platform_auth_cookie(platform: str, cookies: list[dict[str, Any]]) -> bool:
    expected = PLATFORM_AUTH_COOKIES.get(platform)
    if not expected:
        return bool(cookies)
    names = {cookie.get("name") for cookie in cookies}
    return any(name in names for name in expected)


def looks_logged_in_for_platform(
    platform: str,
    *,
    check_url: str,
    final_url: str,
    cookies: list[dict[str, Any]],
) -> bool:
    if not cookies:
        return False

    if has_platform_auth_cookie(platform, cookies):
        return True

    check_host = urlparse(check_url).netloc.lower()
    final_host = urlparse(final_url).netloc.lower()
    final_path = urlparse(final_url).path.lower()

    if check_host and final_host and check_host not in final_host:
        return False

    login_markers = ("login", "signin", "sign-in", "checkpoint", "authwall")
    return not any(marker in final_path for marker in login_markers)
