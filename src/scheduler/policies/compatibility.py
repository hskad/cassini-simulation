"""Vanilla model: apply the optimizer's proposed alignment."""
from .base import ShiftDecision


def accept_change(decision: ShiftDecision) -> bool:
    return True
