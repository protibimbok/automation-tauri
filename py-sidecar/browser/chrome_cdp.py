"""Launch installed Chrome with a persistent profile and control it over CDP."""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from playwright.async_api import Browser, BrowserContext, Page, Playwright

CHROME_PROFILE_DIRNAME = "chrome-profile"

# Fixed layout viewport used for both headed and headless runs. Chrome's window
# can be resized freely; CDP device-metrics override keeps window.innerWidth/Height
# and responsive breakpoints stable.
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 900

# Replaces the deprecated --disable-blink-features=AutomationControlled flag.
STEALTH_INIT_SCRIPT = """
(() => {
  if (Object.getPrototypeOf(navigator).hasOwnProperty("webdriver")) {
    delete Object.getPrototypeOf(navigator).webdriver;
  }
})();
"""


def chrome_profile_path(session_dir: str | Path) -> Path:
    return Path(session_dir) / CHROME_PROFILE_DIRNAME


def system_chrome_profile_dir() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            return Path(local) / "Google" / "Chrome" / "User Data"
        return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    return Path.home() / ".config" / "google-chrome"


def profile_is_in_use(profile_dir: Path) -> bool:
    lock = profile_dir / "SingletonLock"
    if not lock.exists():
        return False

    pid = _lock_target_pid(lock)
    if pid is None:
        return False
    return _process_alive(pid)


def _chrome_candidates() -> list[Path]:
    if sys.platform == "win32":
        roots = [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        return [
            Path(root) / "Google/Chrome/Application/chrome.exe"
            for root in roots
            if root
        ]

    if sys.platform == "darwin":
        return [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path.home()
            / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]

    return [
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/snap/bin/chromium"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
    ]


def _chrome_from_windows_registry() -> Path | None:
    if sys.platform != "win32":
        return None

    import winreg

    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"),
    )
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "")
                path = Path(str(value))
                if path.is_file():
                    return path
        except OSError:
            continue
    return None


def find_chrome_executable() -> Path:
    registry_path = _chrome_from_windows_registry()
    if registry_path is not None:
        return registry_path

    for candidate in _chrome_candidates():
        if candidate.is_file():
            return candidate

    on_path = shutil.which("google-chrome") or shutil.which("chrome")
    if on_path:
        return Path(on_path)

    raise FileNotFoundError(
        "Google Chrome was not found. Install Chrome and try again."
    )


def chrome_installed() -> bool:
    try:
        find_chrome_executable()
        return True
    except FileNotFoundError:
        return False


def _allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _probe_cdp(url: str) -> None:
    with urllib.request.urlopen(url, timeout=2) as response:
        if response.status != 200:
            raise OSError(f"unexpected CDP status {response.status}")


async def _wait_for_cdp(
    port: int,
    process: subprocess.Popen[Any],
    *,
    stderr: TextIO | None = None,
    timeout: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            detail = _read_process_stderr(stderr)
            if "existing browser session" in detail.lower():
                raise RuntimeError(
                    "Chrome is already running with this profile. "
                    "Close other Chrome windows or use an isolated session."
                )
            if "non-default data directory" in detail.lower():
                raise RuntimeError(
                    "Chrome refused remote debugging for the default system profile. "
                    "Use Default Chrome or an isolated session profile instead."
                )
            raise RuntimeError(
                f"Chrome exited before CDP was ready (code {exit_code}){detail}"
            )

        try:
            await asyncio.to_thread(_probe_cdp, url)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            await asyncio.sleep(0.25)

    detail = _read_process_stderr(stderr)
    raise RuntimeError(
        f"Chrome CDP did not become ready on port {port}: {last_error}{detail}"
    )


def _read_process_stderr(stderr: TextIO | None) -> str:
    if stderr is None:
        return ""
    try:
        stderr.flush()
        stderr.seek(0)
        text = stderr.read().strip()
    except (OSError, ValueError):
        return ""
    if not text:
        return ""
    tail = text[-2000:]
    return f": {tail}"


def _lock_target_pid(lock_path: Path) -> int | None:
    try:
        target = os.readlink(lock_path)
    except OSError:
        return None
    if "-" not in target:
        return None
    pid_str = target.rsplit("-", 1)[-1]
    try:
        return int(pid_str)
    except ValueError:
        return None


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def clear_profile_locks(profile_dir: Path, *, require_idle: bool = True) -> None:
    """Remove Chrome singleton files so a new process can open *profile_dir*."""
    lock = profile_dir / "SingletonLock"
    if require_idle and lock.exists():
        pid = _lock_target_pid(lock)
        if pid is not None and _process_alive(pid):
            raise RuntimeError(
                "Chrome is already running with this profile. "
                "Close the open browser window or stop the other session first."
            )

    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        path = profile_dir / name
        if not path.exists():
            continue
        try:
            path.unlink()
        except OSError:
            pass


def _clear_stale_profile_lock(profile_dir: Path) -> None:
    clear_profile_locks(profile_dir, require_idle=True)


def _prepare_profile(profile_dir: Path, *, fresh: bool) -> Path:
    if fresh:
        _reset_profile(profile_dir)
        return profile_dir

    profile_dir.mkdir(parents=True, exist_ok=True)
    _clear_stale_profile_lock(profile_dir)
    return profile_dir


def _reset_profile(profile_dir: Path) -> None:
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)


async def apply_fixed_viewport(
    page: Page,
    *,
    width: int = DEFAULT_VIEWPORT_WIDTH,
    height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> None:
    await page.set_viewport_size({"width": width, "height": height})


async def _wire_stealth(context: BrowserContext) -> None:
    await context.add_init_script(STEALTH_INIT_SCRIPT)


def _wire_fixed_viewport(
    context: BrowserContext,
    *,
    width: int = DEFAULT_VIEWPORT_WIDTH,
    height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> None:
    async def _on_page(page: Page) -> None:
        await apply_fixed_viewport(page, width=width, height=height)

    def _schedule(page: Page) -> None:
        asyncio.create_task(_on_page(page))

    context.on("page", _schedule)


def _chrome_launch_args(
    *,
    chrome_exe: Path,
    profile_dir: Path,
    port: int,
    headless: bool,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> list[str]:
    args = [
        str(chrome_exe),
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        f"--window-size={viewport_width},{viewport_height}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
    ]
    if headless:
        args.append("--headless=new")
    else:
        if sys.platform == "win32":
            # Exit when the last window closes instead of lingering in the tray.
            args.append("--disable-features=BackgroundMode")
        if sys.platform == "linux":
            args.extend(
                [
                    "--disable-dev-shm-usage",
                    "--ozone-platform=x11",
                ]
            )
    return args


def _spawn_chrome(args: list[str]) -> tuple[subprocess.Popen[Any], TextIO]:
    stderr_handle = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": stderr_handle,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(args, **kwargs)
    return process, stderr_handle


@dataclass
class ChromeCdpSession:
    browser: Browser | None
    context: BrowserContext
    page: Page
    process: subprocess.Popen[Any]
    port: int
    profile_dir: Path
    connected_over_cdp: bool = True


async def launch_chrome_cdp(
    playwright: Playwright,
    *,
    profile_dir: Path,
    headless: bool = False,
    fresh: bool = False,
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
) -> ChromeCdpSession:
    """Start Chrome with a dedicated profile directory and attach over CDP."""
    resolved_profile = _prepare_profile(profile_dir, fresh=fresh)

    chrome_exe = find_chrome_executable()
    port = _allocate_port()
    args = _chrome_launch_args(
        chrome_exe=chrome_exe,
        profile_dir=resolved_profile,
        port=port,
        headless=headless,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )
    process, stderr_handle = _spawn_chrome(args)

    try:
        await _wait_for_cdp(port, process, stderr=stderr_handle)
        browser = await playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}"
        )
    except Exception:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        clear_profile_locks(resolved_profile, require_idle=False)
        raise
    finally:
        stderr_handle.close()

    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    await _wire_stealth(context)
    _wire_fixed_viewport(
        context, width=viewport_width, height=viewport_height
    )
    await apply_fixed_viewport(
        page, width=viewport_width, height=viewport_height
    )

    return ChromeCdpSession(
        browser=browser,
        context=context,
        page=page,
        process=process,
        port=port,
        profile_dir=resolved_profile,
    )


async def shutdown_chrome_cdp(session: ChromeCdpSession | None) -> None:
    """Disconnect Playwright and stop the Chrome process."""
    if session is None:
        return

    browser = session.browser
    session.browser = None

    if browser is not None:
        try:
            if browser.is_connected():
                await browser.close()
        except Exception:
            pass

    process = session.process
    profile_dir = session.profile_dir
    if process.poll() is None:
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, 5)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait)

    if profile_dir is not None:
        clear_profile_locks(profile_dir, require_idle=False)
