import pytest

from core.risk import RiskTransitionError, validate_transition


def test_green_to_yellow_allowed():
    validate_transition("GREEN", "YELLOW")


def test_yellow_to_red_allowed():
    validate_transition("YELLOW", "RED")


def test_yellow_back_to_green_allowed():
    validate_transition("YELLOW", "GREEN")


def test_green_to_red_blocked():
    with pytest.raises(RiskTransitionError):
        validate_transition("GREEN", "RED")


def test_red_is_terminal():
    with pytest.raises(RiskTransitionError):
        validate_transition("RED", "GREEN")
