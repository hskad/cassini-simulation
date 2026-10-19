"""Accept only an estimated mean time saving above the requested margin."""
from src.scheduler.shift_policy import estimate_shift_change
from .base import ShiftDecision


def accept_change(decision: ShiftDecision) -> bool:
    if decision.current_score is None:
        raise ValueError("Benefit rule requires the current compatibility score.")
    estimate = estimate_shift_change(
        decision.remaining_work_ms, decision.pending_wait_ms, decision.added_wait_ms,
        current_score=decision.current_score, proposed_score=decision.proposed_score,
        penalty=decision.penalty)
    return estimate.gain_ms > decision.min_gain_ms
