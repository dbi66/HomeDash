from __future__ import annotations

from collections.abc import Callable
from typing import Any


RenderReport = Callable[[Any, list[dict[str, object]]], None]


def render_heat_pump_page(
    snapshot: Any,
    history: list[dict[str, object]],
    render_report: RenderReport,
) -> None:
    """Page boundary for the read-only heat-pump report."""
    render_report(snapshot, history)
