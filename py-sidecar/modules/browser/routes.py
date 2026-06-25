"""Sidecar request handlers for browser control."""

from __future__ import annotations

import subprocess
from typing import Any

from browser.install import chrome_installed, install_chrome
from browser.instance import BrowserRunInfo
from browser.registry import get_registry
from runtime import Daemon, Tauri


def _headless_from_payload(payload: Any) -> bool:
    if isinstance(payload, dict):
        return bool(payload.get("headless", True))
    return True


def _run_id_from_payload(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("run_id")
        if value is not None:
            return str(value)
    return None


def _action_from_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        value = payload.get("action")
        if value is not None:
            return str(value)
    raise RuntimeError("control action is required")


def _run_to_dict(info: BrowserRunInfo) -> dict[str, Any]:
    return {
        "ok": True,
        "run_id": info.run_id,
        "running": info.running,
        "headless": info.headless,
        "url": info.url,
        "paused": info.paused,
        "crashed": info.crashed,
    }


_registry = get_registry()
_registry.set_emit(Tauri.dispatch)


async def browser_launch(payload: Any) -> dict[str, Any]:
    headless = _headless_from_payload(payload)
    info = await _registry.launch(headless=headless)
    return _run_to_dict(info)


async def browser_stop(payload: Any) -> dict[str, Any]:
    run_id = _run_id_from_payload(payload)
    if run_id is None:
        raise RuntimeError("run_id is required")
    info = await _registry.stop(run_id=run_id)
    return _run_to_dict(info)


async def browser_status(payload: Any) -> dict[str, Any]:
    run_id = _run_id_from_payload(payload)
    result = await _registry.status(run_id=run_id)
    if isinstance(result, list):
        return {"ok": True, "instances": [_run_to_dict(i) for i in result]}
    return _run_to_dict(result)


async def browser_recover(payload: Any) -> dict[str, Any]:
    run_id = _run_id_from_payload(payload)
    if run_id is None:
        raise RuntimeError("run_id is required")
    info = await _registry.recover(run_id=run_id)
    return _run_to_dict(info)


async def browser_control(payload: Any) -> dict[str, Any]:
    run_id = _run_id_from_payload(payload)
    if run_id is None:
        raise RuntimeError("run_id is required")
    action = _action_from_payload(payload)
    info = _registry.apply_control(run_id=run_id, action=action)
    return _run_to_dict(info)


async def browser_install_status(_payload: Any) -> dict[str, Any]:
    try:
        installed = await chrome_installed()
    except Exception:
        installed = False
    return {"ok": True, "installed": installed}


async def browser_install_run(_payload: Any) -> dict[str, Any]:
    def on_progress(progress: dict[str, Any]) -> None:
        Tauri.dispatch("browser.install.progress", progress)

    try:
        await install_chrome(on_progress=on_progress)
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "installed": await chrome_installed(),
            "error": f"Google Chrome install failed (exit {exc.returncode})",
        }
    except Exception as exc:
        return {
            "ok": False,
            "installed": await chrome_installed(),
            "error": str(exc),
        }
    return {"ok": True, "installed": await chrome_installed()}


Daemon.route("browser.launch", browser_launch)
Daemon.route("browser.stop", browser_stop)
Daemon.route("browser.status", browser_status)
Daemon.route("browser.recover", browser_recover)
Daemon.route("browser.control", browser_control)
Daemon.route("browser.install.status", browser_install_status)
Daemon.route("browser.install.run", browser_install_run)
