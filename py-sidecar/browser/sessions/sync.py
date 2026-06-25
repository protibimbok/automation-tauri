"""Copy login state from the installed Chrome profile into a session profile."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..chrome_cdp import (
    clear_profile_locks,
    profile_is_in_use,
    system_chrome_profile_dir,
)

# Cookie encryption key lives in Local State; cookie DBs live under Default/.
_PROFILE_SYNC_PATHS = (
    "Local State",
    "Default/Cookies",
    "Default/Cookies-journal",
    "Default/Network/Cookies",
    "Default/Network/Cookies-journal",
    "Default/Preferences",
    "Default/Secure Preferences",
)


@dataclass(frozen=True)
class ProfileSyncResult:
    files_copied: int
    source: Path
    target: Path


def sync_system_chrome_profile(target_profile: Path) -> ProfileSyncResult:
    """Copy cookies and related state from system Chrome into *target_profile*."""
    source = system_chrome_profile_dir()
    if not source.is_dir():
        raise RuntimeError(
            f"System Chrome profile was not found at {source}. "
            "Install Chrome and sign in at least once."
        )

    if profile_is_in_use(source):
        raise RuntimeError(
            "Google Chrome is still running. Close all Chrome windows before syncing."
        )

    if profile_is_in_use(target_profile):
        raise RuntimeError(
            "The Default Chrome session browser is still open. Close it before syncing."
        )

    target_profile.mkdir(parents=True, exist_ok=True)
    copied = 0
    for relative in _PROFILE_SYNC_PATHS:
        src = source / relative
        if not src.is_file():
            continue
        dst = target_profile / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    clear_profile_locks(target_profile, require_idle=False)

    if copied == 0:
        raise RuntimeError(
            "No cookie data found in your system Chrome profile. "
            "Sign in to sites in Chrome first, then sync again."
        )

    return ProfileSyncResult(files_copied=copied, source=source, target=target_profile)
