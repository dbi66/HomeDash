from __future__ import annotations

import random
import signal
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar


ReturnValue = TypeVar("ReturnValue")


@contextmanager
def _operation_timeout(seconds: float | None):
    if seconds is None:
        yield
        return
    if seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("timeout_seconds requires the main thread")

    def raise_timeout(_signum: int, _frame: object) -> None:
        raise TimeoutError(f"operation exceeded {seconds:g} seconds")

    previous_handler = signal.signal(signal.SIGALRM, raise_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def retry_call(
    operation: Callable[[], ReturnValue],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 2.0,
    max_delay_seconds: float = 60.0,
    timeout_seconds: float | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> ReturnValue:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    for attempt in range(attempts):
        try:
            with _operation_timeout(timeout_seconds):
                return operation()
        except Exception:
            if attempt == attempts - 1:
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2**attempt))
            sleep(delay + random_value() * delay * 0.25)

    raise RuntimeError("retry operation did not return")
