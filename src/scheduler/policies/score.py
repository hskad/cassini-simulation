"""Comparison control: require a strictly better compatibility score."""
from .base import ShiftDecision


def accept_change(decision: ShiftDecision) -> bool:
    if decision.current_score is None:
        raise ValueError("Score control requires the current compatibility score.")
    return decision.proposed_score > decision.current_score + 1e-9
