from __future__ import annotations

from app.data.emergency_detection import EMERGENCY_RESPONSE_TEMPLATE, maybe_get_emergency_response


def test_emergency_symptoms_trigger_rule_based_response() -> None:
    query = "Patient has trouble breathing and is becoming lethargic"

    result = maybe_get_emergency_response(query)

    assert result == EMERGENCY_RESPONSE_TEMPLATE
