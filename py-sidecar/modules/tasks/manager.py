"""Spawns and controls running task instances, keyed by run id."""

from __future__ import annotations

import asyncio
from typing import Any

from .base import BaseTask, EmitFn, TaskContext, TaskInput
from .registry import get_task_factory
from .runner import TaskRunner


def _to_inputs(raw: Any) -> list[TaskInput]:
    inputs: list[TaskInput] = []
    if not isinstance(raw, list):
        return inputs
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        inputs.append(
            TaskInput(
                input_id=str(item.get("input_id") or ""),
                ordinal=int(item.get("ordinal") or index),
                data=item.get("data") or {},
                cursor=item.get("cursor") if isinstance(item.get("cursor"), dict) else None,
                seen_keys=list(item.get("seen_keys") or []),
            )
        )
    return inputs


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, BaseTask] = {}
        self._emit: EmitFn | None = None

    def set_emit(self, emit: EmitFn) -> None:
        self._emit = emit

    async def start(
        self,
        run_id: str,
        task_key: str,
        params: dict[str, Any],
        inputs: Any,
        resume: bool = False,
    ) -> dict[str, Any]:
        if not run_id:
            return {"ok": False, "running": False, "error": "run_id is required"}
        if run_id in self._tasks:
            return {"ok": True, "running": True, "found": True}

        try:
            factory = get_task_factory(task_key)
        except ValueError as exc:
            return {"ok": False, "running": False, "error": str(exc)}

        ctx = TaskContext(run_id, task_key, params, _to_inputs(inputs), self._emit)
        task = factory(ctx)
        self._tasks[run_id] = task
        asyncio.get_running_loop().create_task(self._run(run_id, task, ctx, resume))
        return {"ok": True, "running": True, "found": True}

    async def _run(
        self,
        run_id: str,
        task: BaseTask,
        ctx: TaskContext,
        resume: bool,
    ) -> None:
        ctx.status("running")
        if resume:
            ctx.log("Resuming from saved checkpoint")
        try:
            await TaskRunner().run(task, ctx)
            if task.control.stopped:
                ctx.status("stopped")
            else:
                ctx.status("completed")
        except Exception as exc:  # noqa: BLE001 - report any task failure to the host
            ctx.log(f"Task failed: {exc}", level="error")
            ctx.status("failed", error=str(exc))
        finally:
            self._tasks.pop(run_id, None)

    def control(self, run_id: str, action: str) -> dict[str, Any]:
        task = self._tasks.get(run_id)
        if task is None:
            return {"ok": True, "found": False, "running": False}
        if action == "pause":
            task.control.pause()
            task.ctx.status("paused")
        elif action == "resume":
            task.control.resume()
            task.ctx.status("running")
        elif action == "stop":
            task.control.stop()
        else:
            return {"ok": False, "found": True, "error": f"unknown action '{action}'"}
        return {"ok": True, "found": True}


_manager = TaskManager()


def get_task_manager() -> TaskManager:
    return _manager
