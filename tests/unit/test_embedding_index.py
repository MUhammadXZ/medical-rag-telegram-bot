from __future__ import annotations

import json
from pathlib import Path

import math

from app.data.ingestion.models import IngestionConfig
from app.data.ingestion.pipeline import build_faiss_index, load_faiss_index, rebuild_index


class _FakeEmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _FakeEmbeddingResponse:
    def __init__(self, data: list[_FakeEmbeddingItem]) -> None:
        self.data = data


class _FakeEmbeddingsAPI:
    def create(self, model: str, input: list[str]) -> _FakeEmbeddingResponse:
        vectors = [[float(i + 1), float(len(text) + 1)] for i, text in enumerate(input)]
        return _FakeEmbeddingResponse([_FakeEmbeddingItem(v) for v in vectors])


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


class _FakeIndexFlatIP:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors: list[list[float]] | None = None

    def add(self, vectors) -> None:
        rows = vectors.tolist() if hasattr(vectors, "tolist") else vectors
        self.vectors = [list(row) for row in rows]


class _FakeFaiss:
    def __init__(self) -> None:
        self.index: _FakeIndexFlatIP | None = None

    @staticmethod
    def normalize_L2(vectors) -> None:
        as_list = vectors.tolist() if hasattr(vectors, "tolist") else vectors
        normalized: list[list[float]] = []
        for row in as_list:
            norm = math.sqrt(sum(v * v for v in row)) or 1.0
            normalized.append([v / norm for v in row])

        if hasattr(vectors, "tolist"):
            for i, row in enumerate(normalized):
                vectors[i] = row
        else:
            vectors[:] = normalized

    def IndexFlatIP(self, dim: int) -> _FakeIndexFlatIP:
        self.index = _FakeIndexFlatIP(dim)
        return self.index

    @staticmethod
    def write_index(index: _FakeIndexFlatIP, path: str) -> None:
        Path(path).write_text(f"dim={index.dim};count={0 if index.vectors is None else len(index.vectors)}", encoding="utf-8")

    @staticmethod
    def read_index(path: str) -> dict[str, str]:
        raw = Path(path).read_text(encoding="utf-8")
        values = dict(item.split("=") for item in raw.split(";"))
        return values


def test_build_faiss_index_saves_index_and_metadata(tmp_path: Path, monkeypatch, caplog) -> None:
    fake_faiss = _FakeFaiss()
    monkeypatch.setattr("app.data.ingestion.pipeline._get_faiss_module", lambda: fake_faiss)

    records = [
        {"id": "a", "text": "alpha", "metadata": {"section": "S1"}},
        {"id": "b", "text": "beta", "metadata": {"section": "S2"}},
    ]

    caplog.set_level("INFO")
    index_path, metadata_path = build_faiss_index(
        records,
        output_dir=tmp_path,
        embedding_client=_FakeClient(),
    )

    assert index_path.exists()
    assert index_path.stat().st_size > 0
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["embedding_model"] == "text-embedding-3-small"
    assert metadata["dimension"] == 2
    assert [item["id"] for item in metadata["records"]] == ["a", "b"]

    assert fake_faiss.index is not None
    assert fake_faiss.index.vectors is not None
    norms = [math.sqrt(sum(v * v for v in row)) for row in fake_faiss.index.vectors]
    assert all(abs(n - 1.0) < 1e-6 for n in norms)

    assert "Building embeddings for 2 chunks." in caplog.text
    assert "Embedding generation completed in" in caplog.text


def test_rebuild_index_ingests_and_builds(tmp_path: Path, monkeypatch) -> None:
    sample = tmp_path / "guideline_2024.txt"
    sample.write_text("INTRO\nSentence one. Sentence two.", encoding="utf-8")

    fake_faiss = _FakeFaiss()
    monkeypatch.setattr("app.data.ingestion.pipeline._get_faiss_module", lambda: fake_faiss)

    index_path, metadata_path = rebuild_index(
        source_path=sample,
        output_dir=tmp_path / "out",
        config=IngestionConfig(chunk_size_tokens=8, overlap_ratio=0.1),
        embedding_client=_FakeClient(),
    )

    assert index_path.exists()
    assert index_path.stat().st_size > 0
    assert metadata_path.exists()
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["records"]


def test_load_faiss_index_reads_index_and_metadata(tmp_path: Path, monkeypatch) -> None:
    fake_faiss = _FakeFaiss()
    monkeypatch.setattr("app.data.ingestion.pipeline._get_faiss_module", lambda: fake_faiss)

    records = [
        {"id": "a", "text": "alpha", "metadata": {"section": "S1"}},
        {"id": "b", "text": "beta", "metadata": {"section": "S2"}},
    ]

    index_path, metadata_path = build_faiss_index(
        records,
        output_dir=tmp_path,
        embedding_client=_FakeClient(),
    )

    loaded_index, loaded_metadata = load_faiss_index(index_path, metadata_path)

    assert loaded_index["dim"] == "2"
    assert loaded_index["count"] == "2"
    assert len(loaded_metadata["records"]) == 2
