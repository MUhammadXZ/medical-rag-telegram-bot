from __future__ import annotations

from pathlib import Path

from .chunker import build_chunks
from .loaders import load_guideline_documents
from .models import IngestionConfig
from .text_processing import clean_text


def ingest_guidelines(path: str | Path, config: IngestionConfig | None = None) -> list[dict[str, object]]:
    config = config or IngestionConfig()
    documents = load_guideline_documents(path)

    embedding_records: list[dict[str, object]] = []
    for document in documents:
        document.text = clean_text(document.text)
        chunks = build_chunks(document, config)
        embedding_records.extend(chunk.as_embedding_record() for chunk in chunks)

    return embedding_records
