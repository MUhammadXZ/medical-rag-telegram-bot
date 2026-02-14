from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Sequence


@dataclass
class EmbeddingItem:
    embedding: list[float]


@dataclass
class EmbeddingResponse:
    data: list[EmbeddingItem]


class _SentenceTransformerEmbeddingsAPI:
    def __init__(self) -> None:
        self._models: dict[str, object] = {}

    def _load_model(self, model: str) -> object:
        if model in self._models:
            return self._models[model]

        sentence_transformers = importlib.import_module("sentence_transformers")
        sentence_transformer_cls = getattr(sentence_transformers, "SentenceTransformer")
        loaded = sentence_transformer_cls(model)
        self._models[model] = loaded
        return loaded

    def create(self, model: str, input: Sequence[str]) -> EmbeddingResponse:
        transformer = self._load_model(model)
        vectors = transformer.encode(list(input), normalize_embeddings=False)

        if hasattr(vectors, "tolist"):
            vector_rows = vectors.tolist()
        else:
            vector_rows = vectors

        return EmbeddingResponse(data=[EmbeddingItem(embedding=[float(v) for v in row]) for row in vector_rows])


class SentenceTransformerEmbeddingClient:
    """OpenAI-compatible local embeddings client backed by sentence-transformers."""

    def __init__(self) -> None:
        self.embeddings = _SentenceTransformerEmbeddingsAPI()


def sentence_transformers_available() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None
