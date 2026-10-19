"""Comparison control: leave a minimum interval between accepted changes."""
from .base import ShiftDecision


def accept_change(decision: ShiftDecision) -> bool:
    return decision.elapsed_ms >= decision.cooldown_ms
