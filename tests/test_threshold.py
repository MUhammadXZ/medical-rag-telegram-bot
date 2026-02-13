from __future__ import annotations

from app.data.retrieval import retrieve_chunks


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


class _FakeEmbeddingsAPI:
    def create(self, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        return _FakeEmbeddingResponse([_FakeEmbeddingItem([0.1, 0.0])])


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


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


def test_unknown_query_is_rejected_below_threshold() -> None:
    index = _FakeIndex(vectors=[[0.6, 0.0], [0.5, 0.0]])
    metadata = {
        "records": [
            {"id": "chunk-1", "text": "Known content", "metadata": {}},
            {"id": "chunk-2", "text": "Known content 2", "metadata": {}},
        ]
    }

    result = retrieve_chunks(
        query="unknown question",
        index=index,
        metadata=metadata,
        embedding_client=_FakeClient(),
        min_similarity=0.75,
    )

    assert result["rejected"] is True
    assert result["retrieved"] == []
    assert result["max_similarity"] < 0.75
