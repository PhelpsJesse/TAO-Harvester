from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionLimits:
    max_harvest_tao_per_run: float
    max_harvest_tao_per_day: float


def enforce_non_negative(value: float) -> float:
    return value if value > 0 else 0.0
