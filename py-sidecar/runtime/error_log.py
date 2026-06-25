from __future__ import annotations

import sys


def error_log(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)
