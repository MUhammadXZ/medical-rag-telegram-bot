from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.eval.framework import evaluate, load_gold_cases, load_predictions, write_metrics_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline RAG evaluation.")
    parser.add_argument(
        "--gold",
        default="eval/gold_questions.csv",
        help="CSV containing question_id, question, gold_answer, gold_chunk_ids.",
    )
    parser.add_argument(
        "--predictions",
        default="eval/predictions.csv",
        help=(
            "CSV containing question_id, generated_answer, retrieved_chunk_ids, "
            "refused, hallucinated, response_time_ms."
        ),
    )
    parser.add_argument(
        "--output",
        default="eval/metrics.csv",
        help="Output CSV path for aggregate metrics.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    gold_cases = load_gold_cases(args.gold)
    predictions = load_predictions(args.predictions)
    metrics = evaluate(gold_cases, predictions)
    write_metrics_csv(metrics, args.output)

    print(f"Evaluation complete for {metrics.total_questions} questions.")
    print(f"Metrics written to: {args.output}")


if __name__ == "__main__":
    main()
