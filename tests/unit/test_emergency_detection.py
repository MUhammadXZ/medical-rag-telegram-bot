from __future__ import annotations

from app.data.emergency_detection import (
    EMERGENCY_RESPONSE_TEMPLATE,
    is_emergency_query,
    maybe_get_emergency_response,
)


def test_detects_single_red_flags() -> None:
    assert is_emergency_query("Patient has breathing difficulty since morning") is True
    assert is_emergency_query("New facial swelling after medication") is True
    assert is_emergency_query("There was a loss of consciousness") is True


def test_detects_repeated_vomiting_with_lethargy_only_when_both_present() -> None:
    assert is_emergency_query("Child has repeated vomiting and lethargy") is True
    assert is_emergency_query("Child has repeated vomiting") is False
    assert is_emergency_query("Child is lethargic") is False


def test_returns_emergency_template_when_detected() -> None:
    response = maybe_get_emergency_response("My father is unconscious right now")
    assert response == EMERGENCY_RESPONSE_TEMPLATE


def test_returns_none_when_no_red_flag() -> None:
    assert maybe_get_emergency_response("Mild headache after poor sleep") is None
