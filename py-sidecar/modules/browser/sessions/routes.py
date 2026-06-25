"""Sidecar request handlers for persisted browser sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from browser.sessions.manager import SessionRunInfo, get_session_manager
from runtime import Daemon, Tauri


def _session_id(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("session_id"):
        return str(payload["session_id"])
    raise ValueError("session_id is required")


def _session_dir(payload: Any) -> Path:
    session_id = _session_id(payload)
    if isinstance(payload, dict) and payload.get("session_dir"):
        return Path(str(payload["session_dir"]))
    raise ValueError(f"session_dir is required for session '{session_id}'")


def _run_id(payload: Any) -> str | None:
    if isinstance(payload, dict) and payload.get("run_id"):
        return str(payload["run_id"])
    return None


def _check_url(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("check_url"):
        return str(payload["check_url"])
    raise ValueError("check_url is required")


def _platform(payload: Any) -> str:
    if isinstance(payload, dict) and payload.get("platform"):
        return str(payload["platform"])
    raise ValueError("platform is required")


def _start_url(payload: Any) -> str | None:
    if isinstance(payload, dict) and payload.get("start_url"):
        return str(payload["start_url"])
    return None


def _bool(payload: Any, key: str, default: bool) -> bool:
    if isinstance(payload, dict) and key in payload:
        return bool(payload[key])
    return default


def _run_to_dict(info: SessionRunInfo) -> dict[str, Any]:
    return {
        "ok": True,
        "session_id": info.session_id,
        "run_id": info.run_id,
        "running": info.running,
        "headless": info.headless,
        "url": info.url,
        "crashed": info.crashed,
    }


_manager = get_session_manager()
_manager.set_emit(Tauri.dispatch)


async def session_launch(payload: Any) -> dict[str, Any]:
    session_id = _session_id(payload)
    info = await _manager.launch(
        session_id=session_id,
        session_dir=_session_dir(payload),
        headless=_bool(payload, "headless", False),
        fresh=_bool(payload, "fresh", False),
        start_url=_start_url(payload),
    )
    return _run_to_dict(info)


async def session_stop(payload: Any) -> dict[str, Any]:
    session_id = _session_id(payload)
    run_id = _run_id(payload)
    info = await _manager.stop(
        session_id=session_id,
        session_dir=_session_dir(payload),
        run_id=run_id,
    )
    if info is None:
        return {
            "ok": True,
            "session_id": session_id,
            "run_id": run_id or "",
            "running": False,
            "headless": True,
            "url": "",
            "crashed": False,
        }
    return _run_to_dict(info)


async def session_check(payload: Any) -> dict[str, Any]:
    session_id = _session_id(payload)
    return await _manager.check(
        session_id=session_id,
        session_dir=_session_dir(payload),
        check_url=_check_url(payload),
        platform=_platform(payload),
    )


async def session_status(payload: Any) -> dict[str, Any]:
    session_id = None
    if isinstance(payload, dict) and payload.get("session_id"):
        session_id = str(payload["session_id"])
    result = await _manager.status(session_id=session_id)
    if isinstance(result, list):
        return {"ok": True, "instances": [_run_to_dict(info) for info in result]}
    return _run_to_dict(result)


async def session_sync(payload: Any) -> dict[str, Any]:
    session_id = _session_id(payload)
    return await _manager.sync_system_profile(
        session_id=session_id,
        session_dir=_session_dir(payload),
    )


Daemon.route("session.launch", session_launch)
Daemon.route("session.stop", session_stop)
Daemon.route("session.check", session_check)
Daemon.route("session.sync", session_sync)
Daemon.route("session.status", session_status)
