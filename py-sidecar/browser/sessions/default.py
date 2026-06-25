"""Built-in Default Chrome session (shared profile under the session data dir)."""

from __future__ import annotations

DEFAULT_CHROME_SESSION_ID = "default-chrome"
DEFAULT_CHROME_SESSION_NAME = "Default Chrome"


def is_default_chrome_session(session_id: str) -> bool:
    return session_id == DEFAULT_CHROME_SESSION_ID


def uses_system_profile(session_id: str) -> bool:
    """True for the built-in Default Chrome session row."""
    return is_default_chrome_session(session_id)
