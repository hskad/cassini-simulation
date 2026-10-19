"""Selectable shift rules, each implemented in its own module."""
from .base import ShiftDecision
from .benefit import accept_change as accept_benefit
from .compatibility import accept_change as accept_compatibility
from .cooldown import accept_change as accept_cooldown
from .score import accept_change as accept_score


SHIFT_POLICIES = {
    "compatibility": accept_compatibility,
    "score": accept_score,
    "cooldown": accept_cooldown,
    "benefit": accept_benefit,
}


def get_shift_policy(name):
    try:
        return SHIFT_POLICIES[name]
    except KeyError:
        raise ValueError("Unknown shift policy.") from None
