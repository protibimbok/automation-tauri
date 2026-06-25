"""Normalize LinkedIn profile inputs into canonical URLs."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_PROFILE_USERNAME_RE = re.compile(r"^[A-Za-z0-9\-_%]+$")


def normalize_profile_url(raw: str) -> str:
    """Accept a full LinkedIn profile URL, path, or vanity username."""
    text = raw.strip()
    if not text:
        raise ValueError("profile_url is required")

    if text.startswith("@"):
        text = text[1:].strip()

    lower = text.lower()
    if lower.startswith("linkedin.com/") or lower.startswith("www.linkedin.com/"):
        text = f"https://{text}"
    elif lower.startswith("http://") or lower.startswith("https://"):
        pass
    elif text.startswith("/"):
        text = f"https://www.linkedin.com{text}"
    elif text.startswith("in/"):
        text = f"https://www.linkedin.com/{text}"
    elif "/" not in text and _PROFILE_USERNAME_RE.match(text):
        text = f"https://www.linkedin.com/in/{text}/"
    else:
        raise ValueError(
            "profile_url must be a LinkedIn profile URL or username "
            "(e.g. https://www.linkedin.com/in/jane-doe or jane-doe)"
        )

    parsed = urlparse(text)
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in ("linkedin.com", ""):
        raise ValueError(f"unsupported host '{parsed.netloc}' — use linkedin.com")

    path = "/" + parsed.path.strip("/")
    if path == "/":
        raise ValueError("profile_url path is missing")

    if "/recent-activity" in path:
        base = path.split("/recent-activity", 1)[0].rstrip("/") + "/"
        username = _username_from_path(base)
        return f"https://www.linkedin.com/in/{username}/"

    if "/in/" in path:
        username = _username_from_path(path)
        return f"https://www.linkedin.com/in/{username}/"

    if "/company/" in path:
        slug = path.split("/company/", 1)[1].split("/")[0]
        if not slug:
            raise ValueError("company profile slug is missing")
        return f"https://www.linkedin.com/company/{slug}/"

    raise ValueError(
        "profile_url must point to a LinkedIn member (/in/...) or company (/company/...) profile"
    )


def profile_activity_url(raw: str) -> str:
    """Return the recent-activity page for a profile input."""
    text = raw.strip()
    if not text:
        raise ValueError("profile_url is required")

    if text.startswith("@"):
        text = text[1:].strip()

    lower = text.lower()
    if lower.startswith("linkedin.com/") or lower.startswith("www.linkedin.com/"):
        text = f"https://{text}"
    elif not (lower.startswith("http://") or lower.startswith("https://")):
        if text.startswith("/"):
            text = f"https://www.linkedin.com{text}"
        elif text.startswith("in/"):
            text = f"https://www.linkedin.com/{text}"
        elif "/" not in text and _PROFILE_USERNAME_RE.match(text):
            text = f"https://www.linkedin.com/in/{text}/"

    parsed = urlparse(text)
    path = "/" + parsed.path.strip("/")

    if "/recent-activity" in path:
        base = path.split("/recent-activity", 1)[0].rstrip("/")
        if base.startswith("/in/"):
            username = _username_from_path(base + "/")
            return f"https://www.linkedin.com/in/{username}/recent-activity/all/"
        if base.startswith("/company/"):
            slug = base.split("/company/", 1)[1].split("/")[0]
            return f"https://www.linkedin.com/company/{slug}/posts/?viewAsMember=true"
        raise ValueError("could not resolve recent-activity URL")

    profile = normalize_profile_url(raw)
    if "/company/" in profile:
        slug = profile.rstrip("/").split("/company/", 1)[1]
        return f"https://www.linkedin.com/company/{slug}/posts/?viewAsMember=true"

    username = _username_from_path(profile)
    return f"https://www.linkedin.com/in/{username}/recent-activity/all/"


def _username_from_path(path: str) -> str:
    if "/in/" not in path:
        raise ValueError("LinkedIn member username is missing from profile path")
    username = path.split("/in/", 1)[1].split("/")[0].strip()
    if not username:
        raise ValueError("LinkedIn member username is missing from profile path")
    return username
