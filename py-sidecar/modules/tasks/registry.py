"""Registry of task types, keyed by ``{platform}.{task}`` (e.g. linkedin.posts_scraper)."""

from __future__ import annotations

from collections.abc import Callable

from .base import BaseTask, TaskContext

TaskFactory = Callable[[TaskContext], BaseTask]

_TASKS: dict[str, TaskFactory] = {}


def register_task(key: str, factory: TaskFactory | type[BaseTask]) -> None:
    if key in _TASKS:
        raise ValueError(f"task '{key}' is already registered")
    if isinstance(factory, type) and issubclass(factory, BaseTask):
        cls = factory
        factory = lambda ctx: cls(ctx)  # noqa: E731 - tiny class adapter
    _TASKS[key] = factory


def get_task_factory(key: str) -> TaskFactory:
    factory = _TASKS.get(key)
    if factory is None:
        raise ValueError(f"unknown task '{key}'")
    return factory


def registered_tasks() -> list[str]:
    return list(_TASKS.keys())
