from __future__ import annotations

from collections.abc import Callable
from typing import Any


ReportRenderer = Callable[[Any, list[dict[str, object]]], None]


def render_heat_pump_report_page(
    snapshot: Any,
    history: list[dict[str, object]],
    renderer: ReportRenderer,
) -> None:
    """Stable page boundary for the complete read-only heat-pump report."""
    renderer(snapshot, history)
