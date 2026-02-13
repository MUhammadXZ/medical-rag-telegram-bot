from __future__ import annotations

import json
import logging
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - dependency wiring is environment-specific.
    OpenAI = None

from .chunker import build_chunks
from .loaders import load_guideline_documents
from .models import IngestionConfig
from .text_processing import clean_text


logger = logging.getLogger(__name__)


def _get_faiss_module():
    try:
        import faiss
    except ImportError as exc:  # pragma: no cover - dependency wiring is environment-specific.
        raise RuntimeError("faiss is required for index building. Install faiss-cpu/faiss-gpu.") from exc
    return faiss


def _embed_texts(
    texts: list[str],
    model: str,
    embedding_client: OpenAI | object | None,
    batch_size: int = 128,
) -> object:
    if embedding_client is None:
        if OpenAI is None:
            raise RuntimeError("openai package is required for embedding generation.")
        embedding_client = OpenAI()

    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        response = embedding_client.embeddings.create(model=model, input=texts[i : i + batch_size])
        vectors.extend(item.embedding for item in response.data)

    try:
        import numpy as np
    except ImportError:  # pragma: no cover - optional for test/runtime flexibility.
        return vectors

    return np.asarray(vectors, dtype=np.float32)


def build_faiss_index(
    embedding_records: list[dict[str, object]],
    output_dir: str | Path,
    embedding_model: str = "text-embedding-3-small",
    embedding_client: OpenAI | object | None = None,
) -> tuple[Path, Path]:
    if not embedding_records:
        raise ValueError("embedding_records must not be empty.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    texts = [str(record["text"]) for record in embedding_records]
    metadata = [
        {
            "id": record["id"],
            "metadata": record.get("metadata", {}),
            "text": record["text"],
        }
        for record in embedding_records
    ]

    logger.info("Building embeddings for %d chunks.", len(texts))
    started_at = time.perf_counter()
    vectors = _embed_texts(texts, model=embedding_model, embedding_client=embedding_client)
    elapsed = time.perf_counter() - started_at
    logger.info("Embedding generation completed in %.3f seconds.", elapsed)

    faiss = _get_faiss_module()
    faiss.normalize_L2(vectors)
    dimension = len(vectors[0]) if isinstance(vectors, list) else vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)

    index_path = output_path / "guidelines.index"
    metadata_path = output_path / "guidelines_metadata.json"

    faiss.write_index(index, str(index_path))
    metadata_path.write_text(
        json.dumps(
            {
                "embedding_model": embedding_model,
                "dimension": int(dimension),
                "records": metadata,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return index_path, metadata_path


def load_faiss_index(index_path: str | Path, metadata_path: str | Path) -> tuple[object, dict[str, object]]:
    faiss = _get_faiss_module()
    loaded_index = faiss.read_index(str(index_path))
    loaded_metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    return loaded_index, loaded_metadata


def rebuild_index(
    source_path: str | Path,
    output_dir: str | Path,
    config: IngestionConfig | None = None,
    embedding_model: str = "text-embedding-3-small",
    embedding_client: OpenAI | object | None = None,
) -> tuple[Path, Path]:
    records = ingest_guidelines(source_path, config=config)
    return build_faiss_index(
        records,
        output_dir=output_dir,
        embedding_model=embedding_model,
        embedding_client=embedding_client,
    )


def ingest_guidelines(path: str | Path, config: IngestionConfig | None = None) -> list[dict[str, object]]:
    config = config or IngestionConfig()
    documents = load_guideline_documents(path)

    embedding_records: list[dict[str, object]] = []
    for document in documents:
        document.text = clean_text(document.text)
        chunks = build_chunks(document, config)
        embedding_records.extend(chunk.as_embedding_record() for chunk in chunks)

    return embedding_records
