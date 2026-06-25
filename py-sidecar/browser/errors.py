"""Browser error classification."""

from __future__ import annotations


def is_recoverable_browser_error(exc: Exception) -> bool:
    """True when retrying on a fresh browser session may succeed."""
    msg = str(exc).lower()
    return (
        "crashed" in msg
        or "target page, context or browser has been closed" in msg
        or "browser has been closed" in msg
        or "execution context was destroyed" in msg
    )
