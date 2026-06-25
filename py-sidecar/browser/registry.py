"""Registry of browser instances keyed by unique run id."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from .control import RunControl
from .instance import BrowserInstance, BrowserRunInfo

EmitFn = Callable[[str, dict[str, Any]], None]


def _info_payload(info: BrowserRunInfo) -> dict[str, Any]:
    return {
        "ok": True,
        "run_id": info.run_id,
        "running": info.running,
        "headless": info.headless,
        "url": info.url,
        "paused": info.paused,
        "crashed": info.crashed,
    }


class BrowserRegistry:
    """Manages multiple browser instances; each has a unique run id."""

    def __init__(self) -> None:
        self._instances: dict[str, BrowserInstance] = {}
        self._lock = asyncio.Lock()
        self._emit: EmitFn | None = None

    def set_emit(self, emit: EmitFn) -> None:
        self._emit = emit

    def _emit_updated(self, info: BrowserRunInfo) -> None:
        if self._emit is None:
            return
        self._emit("browser.updated", _info_payload(info))

    def _require(self, run_id: str) -> BrowserInstance:
        instance = self._instances.get(run_id)
        if instance is None:
            raise RuntimeError(f"unknown browser run '{run_id}'")
        return instance

    async def launch(self, *, headless: bool = True) -> BrowserRunInfo:
        instance = BrowserInstance(headless=headless, emit=self._emit)
        info = await instance.start()
        async with self._lock:
            self._instances[instance.run_id] = instance
        self._emit_updated(info)
        return info

    async def stop(self, *, run_id: str) -> BrowserRunInfo:
        instance = self._require(run_id)
        info = await instance.stop()
        async with self._lock:
            self._instances.pop(run_id, None)
        self._emit_updated(info)
        return info

    async def recover(self, *, run_id: str) -> BrowserRunInfo:
        instance = self._require(run_id)
        info = await instance.recover()
        self._emit_updated(info)
        return info

    async def status(self, *, run_id: str | None = None) -> BrowserRunInfo | list[BrowserRunInfo]:
        if run_id is not None:
            instance = self._instances.get(run_id)
            if instance is None:
                return BrowserRunInfo(
                    run_id=run_id,
                    headless=True,
                    url="",
                    running=False,
                    crashed=False,
                )
            await instance.refresh()
            if not instance.is_running:
                async with self._lock:
                    self._instances.pop(run_id, None)
            return instance.info()

        results: list[BrowserRunInfo] = []
        stale: list[str] = []
        for rid, instance in list(self._instances.items()):
            await instance.refresh()
            if instance.is_running:
                results.append(instance.info())
            else:
                stale.append(rid)
        if stale:
            async with self._lock:
                for rid in stale:
                    self._instances.pop(rid, None)
        return results

    def get_control(self, run_id: str) -> RunControl:
        return self._require(run_id).control

    def get_instance(self, run_id: str) -> BrowserInstance:
        return self._require(run_id)

    def apply_control(self, *, run_id: str, action: str) -> BrowserRunInfo:
        control = self.get_control(run_id)
        if action == "pause":
            control.pause()
        elif action == "resume":
            control.resume()
        elif action == "stop":
            control.stop()
        else:
            raise RuntimeError(f"unknown control action '{action}'")
        info = self._require(run_id).info()
        self._emit_updated(info)
        return info


_registry = BrowserRegistry()


def get_registry() -> BrowserRegistry:
    return _registry
