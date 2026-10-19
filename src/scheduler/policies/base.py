"""Inputs shared by shift acceptance rules; the simulator owns job state."""
from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class ShiftDecision:
    proposed_score: float
    current_score: Optional[float]
    remaining_work_ms: Mapping[str, float]
    pending_wait_ms: Mapping[str, float]
    added_wait_ms: Mapping[str, float]
    penalty: float
    min_gain_ms: float
    elapsed_ms: float
    cooldown_ms: float
