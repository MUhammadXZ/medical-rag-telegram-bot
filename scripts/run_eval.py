from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.data.ingestion.pipeline import build_faiss_index, ingest_guidelines, load_faiss_index
from app.eval.framework import evaluate_retrieval, load_gold_questions, write_metrics_csv


class _EmbeddingItem:
    def __init__(self, embedding: list[float]) -> None:
        self.embedding = embedding


class _EmbeddingResponse:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self.data = [_EmbeddingItem(embedding) for embedding in embeddings]


class _DeterministicEmbeddingsAPI:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def create(self, model: str, input: list[str]) -> _EmbeddingResponse:
        vectors = [self._to_vector(text) for text in input]
        return _EmbeddingResponse(vectors)

    def _to_vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class DeterministicEmbeddingClient:
    def __init__(self, dimensions: int = 256) -> None:
        self.embeddings = _DeterministicEmbeddingsAPI(dimensions=dimensions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CMPA retrieval evaluation with a real FAISS index.")
    parser.add_argument(
        "--gold",
        default="eval/gold_questions_cmpa.csv",
        help="CSV containing question, expected_keywords, expected_section.",
    )
    parser.add_argument(
        "--output",
        default="eval/metrics.csv",
        help="Output CSV path for aggregate metrics.",
    )
    parser.add_argument(
        "--index-dir",
        default="eval/faiss",
        help="Directory for FAISS index and metadata files.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks considered for top-k accuracy.",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.15,
        help="Similarity threshold below which retrieval is treated as refusal.",
    )
    return parser


def _cmpa_sources() -> list[Path]:
    return [
        ROOT / "cmpa_knowledge.txt",
        ROOT / "medical_guidelines_summary.txt",
        ROOT / "symptom_checker_logic.txt",
        ROOT / "recipes_database.txt",
    ]


def _build_index(index_dir: Path, embedding_client: DeterministicEmbeddingClient) -> tuple[object, dict[str, object]]:
    records = []
    for source in _cmpa_sources():
        records.extend(ingest_guidelines(source))

    index_path, metadata_path = build_faiss_index(
        records,
        output_dir=index_dir,
        embedding_model="deterministic-local",
        embedding_client=embedding_client,
    )
    return load_faiss_index(index_path, metadata_path)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    embedding_client = DeterministicEmbeddingClient()
    index, metadata = _build_index(Path(args.index_dir), embedding_client)
    gold_questions = load_gold_questions(args.gold)

    metrics = evaluate_retrieval(
        gold_questions,
        index,
        metadata,
        embedding_model="deterministic-local",
        embedding_client=embedding_client,
        top_k=args.top_k,
        min_similarity=args.min_similarity,
    )
    write_metrics_csv(metrics, args.output)

    print(f"Evaluation complete for {metrics.total_questions} questions.")
    print(f"Metrics written to: {args.output}")


if __name__ == "__main__":
    main()
