"""Detect and install Google Chrome for browser automation."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from .chrome_cdp import chrome_installed as _chrome_installed_sync
from .chrome_cdp import find_chrome_executable

_INSTALL_LOCK = asyncio.Lock()

_CHROME_INSTALLER_URL_WIN = (
    "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
)
_CHROME_DOWNLOAD_URL_MAC = (
    "https://www.google.com/chrome/?brand=GGRF&platform=mac"
)
_CHROME_DOWNLOAD_URL_LINUX = "https://www.google.com/chrome/"


class InstallProgress(TypedDict):
    message: str
    percent: int | None


ProgressCallback = Callable[[InstallProgress], None]


def _emit_progress(
    on_progress: ProgressCallback | None,
    message: str,
    *,
    percent: int | None = None,
) -> None:
    if on_progress is None:
        return
    on_progress({"message": message, "percent": percent})


def _download_file(
    url: str,
    dest: Path,
    on_progress: ProgressCallback | None,
    *,
    label: str,
    percent_start: int,
    percent_end: int,
) -> None:
    with urllib.request.urlopen(url, timeout=120) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with dest.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                if on_progress is not None and total > 0:
                    ratio = downloaded / total
                    percent = percent_start + int(
                        ratio * max(percent_end - percent_start, 1)
                    )
                    _emit_progress(on_progress, label, percent=min(percent, percent_end))


def _wait_for_chrome_install(
    on_progress: ProgressCallback | None,
    *,
    timeout: float = 180.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _chrome_installed_sync():
            return
        _emit_progress(
            on_progress,
            "Waiting for Google Chrome installation to finish…",
            percent=95,
        )
        time.sleep(2.0)
    raise RuntimeError(
        "Google Chrome install did not complete in time. Finish the installer and retry."
    )


def _install_chrome_windows(on_progress: ProgressCallback | None = None) -> None:
    _emit_progress(
        on_progress,
        "Downloading Google Chrome installer…",
        percent=0,
    )
    with tempfile.TemporaryDirectory() as tmp:
        installer = Path(tmp) / "chrome_installer.exe"
        _download_file(
            _CHROME_INSTALLER_URL_WIN,
            installer,
            on_progress,
            label="Downloading Google Chrome installer…",
            percent_start=0,
            percent_end=55,
        )
        _emit_progress(on_progress, "Installing Google Chrome…", percent=60)
        result = subprocess.run(
            [str(installer), "/silent", "/install"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(detail or "Google Chrome installer failed")

    _emit_progress(on_progress, "Verifying Google Chrome installation…", percent=90)
    _wait_for_chrome_install(on_progress)


def _install_chrome_macos(on_progress: ProgressCallback | None = None) -> None:
    _emit_progress(
        on_progress,
        "Opening the Google Chrome download page…",
        percent=10,
    )
    subprocess.run(["open", _CHROME_DOWNLOAD_URL_MAC], check=False)
    _wait_for_chrome_install(on_progress, timeout=300.0)


def _install_chrome_linux(on_progress: ProgressCallback | None = None) -> None:
    opened = False
    for command in (
        ["xdg-open", _CHROME_DOWNLOAD_URL_LINUX],
        ["gio", "open", _CHROME_DOWNLOAD_URL_LINUX],
        ["wslview", _CHROME_DOWNLOAD_URL_LINUX],
    ):
        try:
            subprocess.run(command, check=False, timeout=10)
            opened = True
            break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if not opened:
        raise RuntimeError(
            "Could not open the Chrome download page automatically. "
            f"Install Chrome from {_CHROME_DOWNLOAD_URL_LINUX}"
        )

    _emit_progress(
        on_progress,
        "Complete the Google Chrome installer, then wait…",
        percent=20,
    )
    _wait_for_chrome_install(on_progress, timeout=300.0)


def _install_chrome_sync(on_progress: ProgressCallback | None = None) -> None:
    if sys.platform == "win32":
        _install_chrome_windows(on_progress)
        return
    if sys.platform == "darwin":
        _install_chrome_macos(on_progress)
        return
    _install_chrome_linux(on_progress)


async def chrome_installed() -> bool:
    try:
        return await asyncio.to_thread(_chrome_installed_sync)
    except Exception:
        return False


async def install_chrome(on_progress: ProgressCallback | None = None) -> None:
    """Install Google Chrome; raises on failure."""
    async with _INSTALL_LOCK:
        if await chrome_installed():
            _emit_progress(on_progress, "Google Chrome is ready.", percent=100)
            return

        await asyncio.to_thread(_install_chrome_sync, on_progress)
        if not await chrome_installed():
            raise RuntimeError(
                "Google Chrome install finished but Chrome could not be found"
            )
        _emit_progress(on_progress, "Google Chrome is ready.", percent=100)


async def ensure_chrome() -> None:
    """Ensure Google Chrome is installed before launching a browser."""
    if await chrome_installed():
        return
    await install_chrome()


def chrome_missing_error() -> str:
    return (
        "Google Chrome is not installed. Install Chrome from the setup screen "
        "and try again."
    )


def require_chrome_executable() -> Path:
    try:
        return find_chrome_executable()
    except FileNotFoundError as exc:
        raise RuntimeError(chrome_missing_error()) from exc
