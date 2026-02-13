from __future__ import annotations

import logging
from typing import Any

from .ingestion.pipeline import _embed_texts


logger = logging.getLogger(__name__)


def retrieve_chunks(
    query: str,
    index: Any,
    metadata: dict[str, object],
    embedding_model: str = "text-embedding-3-small",
    embedding_client: object | None = None,
    top_k: int = 5,
    min_similarity: float = 0.75,
) -> dict[str, object]:
    if not query.strip():
        raise ValueError("query must not be empty.")
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero.")

    records = metadata.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("metadata['records'] must contain indexed records.")

    query_vector = _embed_texts([query], model=embedding_model, embedding_client=embedding_client)

    try:
        import numpy as np

        if isinstance(query_vector, list):
            query_vector = np.asarray(query_vector, dtype=np.float32)

        import faiss

        faiss.normalize_L2(query_vector)
    except ImportError:  # pragma: no cover - optional runtime dependency for pure unit tests.
        pass

    requested_k = min(top_k, len(records))
    distances, indices = index.search(query_vector, requested_k)

    score_row = distances[0].tolist() if hasattr(distances[0], "tolist") else list(distances[0])
    idx_row = indices[0].tolist() if hasattr(indices[0], "tolist") else list(indices[0])

    retrieved: list[dict[str, object]] = []
    retrieved_chunk_ids: list[str] = []
    for rank, chunk_index in enumerate(idx_row):
        if chunk_index < 0:
            continue
        record = records[chunk_index]
        chunk_id = str(record["id"])
        score = float(score_row[rank])

        retrieved_chunk_ids.append(chunk_id)
        retrieved.append(
            {
                "id": chunk_id,
                "text": record.get("text", ""),
                "metadata": record.get("metadata", {}),
                "similarity": score,
            }
        )

    max_similarity = max((item["similarity"] for item in retrieved), default=0.0)
    rejected = max_similarity < min_similarity

    logger.info("Retrieval query: %s", query)
    logger.info("Retrieved chunk ids: %s", retrieved_chunk_ids)
    logger.info("Similarity scores: %s", [round(score, 6) for score in score_row])

    if rejected:
        return {
            "query": query,
            "retrieved": [],
            "similarity_scores": score_row,
            "max_similarity": max_similarity,
            "rejected": True,
        }

    return {
        "query": query,
        "retrieved": retrieved,
        "similarity_scores": score_row,
        "max_similarity": max_similarity,
        "rejected": False,
    }
