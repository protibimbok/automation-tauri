"""Sidecar request handlers for the generic task framework."""

from __future__ import annotations

from typing import Any

from runtime import Daemon, Tauri

from .manager import get_task_manager

_manager = get_task_manager()
_manager.set_emit(Tauri.dispatch)


async def tasks_start(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid payload"}
    return await _manager.start(
        run_id=str(payload.get("run_id") or ""),
        task_key=str(payload.get("task") or ""),
        params=payload.get("params") or {},
        inputs=payload.get("inputs") or [],
        resume=bool(payload.get("resume", False)),
    )


async def tasks_control(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "invalid payload"}
    return _manager.control(
        run_id=str(payload.get("run_id") or ""),
        action=str(payload.get("action") or ""),
    )


Daemon.route("tasks.start", tasks_start)
Daemon.route("tasks.control", tasks_control)
