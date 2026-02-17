from __future__ import annotations

import csv
from pathlib import Path

from app.eval.framework import evaluate_retrieval, load_gold_questions, write_metrics_csv


ROOT = Path(__file__).resolve().parents[2]


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


class _FakeEmbeddingsAPI:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def create(self, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        return _FakeEmbeddingResponse([_FakeEmbeddingItem(self._vector)])


class _FakeClient:
    def __init__(self, vector: list[float]) -> None:
        self.embeddings = _FakeEmbeddingsAPI(vector)


class _FakeIndex:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def search(self, query_vector, top_k: int):
        query = query_vector[0]
        ranked = []
        for idx, row in enumerate(self.vectors):
            score = sum(a * b for a, b in zip(query, row))
            ranked.append((idx, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        selected = ranked[:top_k]
        return [[score for _, score in selected]], [[idx for idx, _ in selected]]


def test_gold_dataset_contains_cmpa_questions() -> None:
    questions = load_gold_questions(ROOT / "eval" / "gold_questions_cmpa.csv")
    assert 40 <= len(questions) <= 50


def test_evaluate_computes_expected_metrics(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.csv"
    metrics_path = tmp_path / "metrics.csv"

    with gold_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["question", "expected_keywords", "expected_section"])
        writer.writerow(["what is cmpa", "cmpa,immune", "definition"])
        writer.writerow(["what are red flags", "anaphylaxis,emergency", "red_flags"])

    metadata = {
        "records": [
            {"id": "C1", "text": "CMPA is an immune response definition", "metadata": {"section": "تعريف"}},
            {"id": "C2", "text": "Anaphylaxis emergency red flags", "metadata": {"section": "علامات حمراء"}},
        ]
    }

    metrics = evaluate_retrieval(
        load_gold_questions(gold_path),
        _FakeIndex([[1.0, 0.0], [0.0, 1.0]]),
        metadata,
        embedding_model="fake",
        embedding_client=_FakeClient([1.0, 0.0]),
        top_k=2,
        min_similarity=0.0,
    )

    assert metrics.total_questions == 2
    assert metrics.retrieval_accuracy_topk == 1.0
    assert metrics.retrieval_accuracy_top1 == 0.5
    assert metrics.refusal_rate == 0.0
    assert metrics.avg_response_time_ms >= 0

    write_metrics_csv(metrics, metrics_path)
    assert metrics_path.exists()
