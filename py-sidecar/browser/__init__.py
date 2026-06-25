"""Playwright browser automation for the Python sidecar."""

from browser.control import ControlledIterator, RunControl, controlled_iterate
from browser.errors import is_recoverable_browser_error
from browser.instance import BrowserInstance, BrowserRunInfo
from browser.registry import BrowserRegistry, get_registry
from browser.wrapper import (
    recover_instance,
    run_controlled_steps,
    with_instance_retry,
    with_page_retry,
)

__all__ = [
    "BrowserInstance",
    "BrowserRegistry",
    "BrowserRunInfo",
    "ControlledIterator",
    "RunControl",
    "controlled_iterate",
    "get_registry",
    "is_recoverable_browser_error",
    "recover_instance",
    "run_controlled_steps",
    "with_instance_retry",
    "with_page_retry",
]
