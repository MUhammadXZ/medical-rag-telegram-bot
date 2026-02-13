from __future__ import annotations

from app.data.retrieval import retrieve_chunks


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


def test_known_query_retrieves_relevant_chunk() -> None:
    index = _FakeIndex(vectors=[[1.0, 0.0], [0.3, 0.0], [0.1, 0.0]])
    metadata = {
        "records": [
            {"id": "known-guideline", "text": "Known clinical guidance", "metadata": {}},
            {"id": "other-1", "text": "Other chunk", "metadata": {}},
            {"id": "other-2", "text": "Other chunk 2", "metadata": {}},
        ]
    }

    result = retrieve_chunks(
        query="known question",
        index=index,
        metadata=metadata,
        embedding_client=_FakeClient([1.0, 0.0]),
        min_similarity=0.75,
    )

    assert result["rejected"] is False
    assert result["retrieved"][0]["id"] == "known-guideline"
