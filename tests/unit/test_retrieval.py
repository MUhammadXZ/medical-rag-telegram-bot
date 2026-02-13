from __future__ import annotations

import math

from app.data.retrieval import retrieve_chunks


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


class _FakeEmbeddingsAPI:
    def create(self, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        query = input[0]
        if "strong" in query:
            vector = [1.0, 0.0]
        else:
            vector = [0.2, 0.0]
        return _FakeEmbeddingResponse([_FakeEmbeddingItem(vector)])


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


class _FakeIndex:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def search(self, query_vector, top_k: int):
        q = query_vector[0]
        similarities = []
        for i, row in enumerate(self.vectors):
            score = sum(a * b for a, b in zip(q, row))
            similarities.append((i, score))

        similarities.sort(key=lambda item: item[1], reverse=True)
        selected = similarities[:top_k]

        distances = [[score for _, score in selected]]
        indices = [[idx for idx, _ in selected]]
        return distances, indices


def _metadata() -> dict[str, object]:
    return {
        "records": [
            {"id": "chunk-1", "text": "first", "metadata": {"section": "A"}},
            {"id": "chunk-2", "text": "second", "metadata": {"section": "B"}},
            {"id": "chunk-3", "text": "third", "metadata": {"section": "C"}},
            {"id": "chunk-4", "text": "fourth", "metadata": {"section": "D"}},
            {"id": "chunk-5", "text": "fifth", "metadata": {"section": "E"}},
            {"id": "chunk-6", "text": "sixth", "metadata": {"section": "F"}},
        ]
    }


def test_retrieval_returns_top_5_with_similarity_scores_and_logs(caplog) -> None:
    index = _FakeIndex(
        vectors=[
            [1.0, 0.0],
            [0.9, 0.0],
            [0.8, 0.0],
            [0.7, 0.0],
            [0.6, 0.0],
            [0.5, 0.0],
        ]
    )

    caplog.set_level("INFO")
    result = retrieve_chunks(
        query="strong match",
        index=index,
        metadata=_metadata(),
        embedding_client=_FakeClient(),
    )

    assert result["rejected"] is False
    assert len(result["retrieved"]) == 5
    assert [item["id"] for item in result["retrieved"]] == [
        "chunk-1",
        "chunk-2",
        "chunk-3",
        "chunk-4",
        "chunk-5",
    ]
    assert result["similarity_scores"] == [1.0, 0.9, 0.8, 0.7, 0.6]

    assert "Retrieval query: strong match" in caplog.text
    assert "Retrieved chunk ids: ['chunk-1', 'chunk-2', 'chunk-3', 'chunk-4', 'chunk-5']" in caplog.text
    assert "Similarity scores: [1.0, 0.9, 0.8, 0.7, 0.6]" in caplog.text


def test_retrieval_rejects_when_max_similarity_is_below_threshold() -> None:
    index = _FakeIndex(vectors=[[0.5, 0.0], [0.4, 0.0], [0.3, 0.0]])

    result = retrieve_chunks(
        query="weak match",
        index=index,
        metadata={
            "records": [
                {"id": "chunk-1", "text": "first", "metadata": {}},
                {"id": "chunk-2", "text": "second", "metadata": {}},
                {"id": "chunk-3", "text": "third", "metadata": {}},
            ]
        },
        embedding_client=_FakeClient(),
    )

    assert result["rejected"] is True
    assert result["retrieved"] == []
    assert math.isclose(result["max_similarity"], 0.1)


def test_retrieval_validates_top_k() -> None:
    index = _FakeIndex(vectors=[[1.0, 0.0]])

    try:
        retrieve_chunks(
            query="strong match",
            index=index,
            metadata={"records": [{"id": "chunk-1", "text": "first", "metadata": {}}]},
            embedding_client=_FakeClient(),
            top_k=0,
        )
    except ValueError as exc:
        assert str(exc) == "top_k must be greater than zero."
    else:
        raise AssertionError("ValueError was not raised for invalid top_k")
