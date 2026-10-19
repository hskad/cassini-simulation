"""Decisions about phase changes under a frozen compatibility-score estimate."""
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ShiftEstimate:
    keep_mean_ms: float
    change_mean_ms: float

    @property
    def gain_ms(self) -> float:
        return self.keep_mean_ms - self.change_mean_ms


def estimate_shift_change(remaining_work_ms: Mapping[str, float],
                          pending_wait_ms: Mapping[str, float],
                          added_wait_ms: Mapping[str, float], *,
                          current_score: float, proposed_score: float,
                          penalty: float) -> ShiftEstimate:
    """Estimate mean remaining time for all affected jobs, including waits.

    Remaining work is nominal time, not an iteration count or future arrivals.
    Each score is held fixed for this estimate; later events may change it.
    """
    if not remaining_work_ms:
        return ShiftEstimate(0.0, 0.0)
    keep_factor = 1 + penalty * (1 - current_score)
    change_factor = 1 + penalty * (1 - proposed_score)
    keep = sum(pending_wait_ms[j] + work * keep_factor
               for j, work in remaining_work_ms.items())
    change = sum(pending_wait_ms[j] + added_wait_ms.get(j, 0.0) + work * change_factor
                 for j, work in remaining_work_ms.items())
    return ShiftEstimate(keep / len(remaining_work_ms), change / len(remaining_work_ms))
