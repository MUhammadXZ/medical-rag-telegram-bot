from __future__ import annotations

from pathlib import Path

import pytest

from app.data.ingestion.pipeline import build_faiss_index, load_faiss_index
from app.data.retrieval import retrieve_chunks


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


class _DeterministicEmbeddingsAPI:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def create(self, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        vectors = [self._mapping[text] for text in input]
        return _FakeEmbeddingResponse([_FakeEmbeddingItem(v) for v in vectors])


class _FakeClient:
    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self.embeddings = _DeterministicEmbeddingsAPI(mapping)


@pytest.mark.integration
def test_end_to_end_rag_retrieval_and_threshold_with_real_faiss(tmp_path: Path) -> None:
    faiss = pytest.importorskip("faiss")

    known_chunk = "Known hypertension guideline chunk"
    other_chunk = "Unrelated nutrition notes"
    known_query = "hypertension management query"
    unknown_query = "astronomy question"

    embedding_map = {
        known_chunk: [1.0, 0.0],
        other_chunk: [0.0, 1.0],
        known_query: [1.0, 0.0],
        unknown_query: [0.2, 0.2],
    }

    records = [
        {"id": "known-guideline", "text": known_chunk, "metadata": {"section": "A"}},
        {"id": "other-guideline", "text": other_chunk, "metadata": {"section": "B"}},
    ]

    client = _FakeClient(embedding_map)
    index_path, metadata_path = build_faiss_index(records, output_dir=tmp_path, embedding_client=client)
    index, metadata = load_faiss_index(index_path, metadata_path)

    # Sanity-check that we are running against the real FAISS path.
    assert faiss is not None
    assert index_path.exists() and metadata_path.exists()

    known_result = retrieve_chunks(
        query=known_query,
        index=index,
        metadata=metadata,
        embedding_client=client,
        min_similarity=0.75,
    )

    assert known_result["rejected"] is False
    assert known_result["retrieved"][0]["id"] == "known-guideline"

    unknown_result = retrieve_chunks(
        query=unknown_query,
        index=index,
        metadata=metadata,
        embedding_client=client,
        min_similarity=0.75,
    )

    assert unknown_result["rejected"] is True
    assert unknown_result["retrieved"] == []
    assert unknown_result["max_similarity"] < 0.75
