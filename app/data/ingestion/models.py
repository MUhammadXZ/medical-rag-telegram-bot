from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class IngestionConfig:
    chunk_size_tokens: int = 400
    overlap_ratio: float = 0.15

    @property
    def overlap_tokens(self) -> int:
        return max(1, int(self.chunk_size_tokens * self.overlap_ratio))


@dataclass(slots=True)
class RawDocument:
    source: Path
    text: str
    year: int | None = None


@dataclass(slots=True)
class Section:
    title: str
    text: str


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    metadata: dict[str, str | int | None] = field(default_factory=dict)

    def as_embedding_record(self) -> dict[str, object]:
        return {
            "id": self.chunk_id,
            "text": self.text,
            "metadata": self.metadata,
        }
