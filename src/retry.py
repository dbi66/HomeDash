from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar


ReturnValue = TypeVar("ReturnValue")


def retry_call(
    operation: Callable[[], ReturnValue],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 2.0,
    max_delay_seconds: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> ReturnValue:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(attempts):
        try:
            return operation()
        except Exception:
            if attempt == attempts - 1:
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2**attempt))
            sleep(delay + random_value() * delay * 0.25)

    raise RuntimeError("retry operation did not return")
