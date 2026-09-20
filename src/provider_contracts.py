from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar


T = TypeVar("T")


class ProviderStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    MISSING = "missing"


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    status: ProviderStatus
    value: T | None = None
    error: str | None = None

    @classmethod
    def success(cls, value: T) -> "ProviderResult[T]":
        return cls(status=ProviderStatus.OK, value=value)

    @classmethod
    def failure(cls, error: str, status: ProviderStatus = ProviderStatus.ERROR) -> "ProviderResult[T]":
        return cls(status=status, error=error)

    @property
    def ok(self) -> bool:
        return self.status == ProviderStatus.OK


def normalize_weather_forecast(payload: Any) -> ProviderResult[dict[str, Any]]:
    if not isinstance(payload, dict) or not payload.get("daily"):
        return ProviderResult.failure("Weather payload missing daily forecast", status=ProviderStatus.DEGRADED)
    return ProviderResult.success(payload)
