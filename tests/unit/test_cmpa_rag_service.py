from __future__ import annotations

from app.services.cmpa_rag_service import CmpaRagService


class _DummyIndex:
    pass


def _build_service() -> CmpaRagService:
    return CmpaRagService(index=_DummyIndex(), metadata={"records": [{"id": "1", "text": "x", "metadata": {}}]})


def test_emergency_response_is_prioritized(monkeypatch) -> None:
    service = _build_service()

    monkeypatch.setattr(
        "app.services.cmpa_rag_service.maybe_get_emergency_response",
        lambda query: "🚨 This may be a medical emergency.",
    )

    answer = service._answer_sync("trouble breathing")

    assert answer.is_emergency is True
    assert "EMERGENCY WARNING" in answer.text


def test_refusal_for_out_of_scope_or_low_similarity(monkeypatch) -> None:
    service = _build_service()

    monkeypatch.setattr("app.services.cmpa_rag_service.maybe_get_emergency_response", lambda query: None)
    monkeypatch.setattr(
        "app.services.cmpa_rag_service.retrieve_chunks",
        lambda **kwargs: {"rejected": True, "retrieved": []},
    )

    answer = service._answer_sync("How do I train for a marathon?")

    assert answer.is_refusal is True
    assert "Scope notice" in answer.text


def test_structured_cmpa_response_contains_sections(monkeypatch) -> None:
    service = _build_service()

    monkeypatch.setattr("app.services.cmpa_rag_service.maybe_get_emergency_response", lambda query: None)
    monkeypatch.setattr(
        "app.services.cmpa_rag_service.retrieve_chunks",
        lambda **kwargs: {
            "rejected": False,
            "retrieved": [
                {
                    "text": "CMPA can present with gastrointestinal and skin symptoms.",
                    "metadata": {"section": "diagnosis"},
                }
            ],
        },
    )

    answer = service._answer_sync("What are common CMPA symptoms?")

    assert answer.is_refusal is False
    assert "*CMPA Guidance*" in answer.text
    assert "*Evidence from CMPA knowledge base*" in answer.text
    assert "• [diagnosis]" in answer.text
