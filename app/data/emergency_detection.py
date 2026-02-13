from __future__ import annotations

import re

EMERGENCY_RESPONSE_TEMPLATE = (
    "🚨 This may be a medical emergency.\n"
    "Seek immediate in-person care now: call your local emergency number or go to the nearest emergency department.\n"
    "If the person is unconscious, has severe breathing trouble, or symptoms are rapidly worsening, call emergency services immediately."
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_emergency_query(message: str) -> bool:
    """Return True when the message contains predefined emergency red flags."""
    normalized = _normalize(message)

    breathing_difficulty = (
        "breathing difficulty" in normalized
        or "difficulty breathing" in normalized
        or "trouble breathing" in normalized
        or "shortness of breath" in normalized
    )
    facial_or_lip_swelling = "facial swelling" in normalized or "lip swelling" in normalized
    loss_of_consciousness = (
        "loss of consciousness" in normalized
        or "lost consciousness" in normalized
        or "unconscious" in normalized
    )

    repeated_vomiting = "repeated vomiting" in normalized or "vomiting repeatedly" in normalized
    lethargy = "lethargy" in normalized or "lethargic" in normalized
    repeated_vomiting_with_lethargy = repeated_vomiting and lethargy

    return any(
        [
            breathing_difficulty,
            facial_or_lip_swelling,
            loss_of_consciousness,
            repeated_vomiting_with_lethargy,
        ]
    )


def maybe_get_emergency_response(message: str) -> str | None:
    """Return emergency template if a red flag is detected, otherwise None."""
    if is_emergency_query(message):
        return EMERGENCY_RESPONSE_TEMPLATE
    return None
