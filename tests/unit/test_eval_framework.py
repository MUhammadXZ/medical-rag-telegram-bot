from __future__ import annotations

import csv
from pathlib import Path

from app.eval.framework import evaluate, load_gold_cases, load_predictions, write_metrics_csv


ROOT = Path(__file__).resolve().parents[2]


def test_gold_dataset_contains_50_questions() -> None:
    gold_cases = load_gold_cases(ROOT / "eval" / "gold_questions.csv")
    assert len(gold_cases) == 50


def test_evaluate_computes_expected_metrics(tmp_path: Path) -> None:
    gold_path = tmp_path / "gold.csv"
    pred_path = tmp_path / "pred.csv"
    metrics_path = tmp_path / "metrics.csv"

    with gold_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["question_id", "question", "gold_answer", "gold_chunk_ids"])
        writer.writerow(["Q1", "q1", "a1", "C1"])
        writer.writerow(["Q2", "q2", "a2", "C2"])

    with pred_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "question_id",
                "generated_answer",
                "retrieved_chunk_ids",
                "refused",
                "hallucinated",
                "response_time_ms",
            ]
        )
        writer.writerow(["Q1", "ans", "C1;C5", "false", "false", "100"])
        writer.writerow(["Q2", "ans", "C9;C2", "true", "true", "200"])

    metrics = evaluate(load_gold_cases(gold_path), load_predictions(pred_path))
    assert metrics.total_questions == 2
    assert metrics.retrieval_accuracy_topk == 1.0
    assert metrics.retrieval_accuracy_top1 == 0.5
    assert metrics.hallucination_rate == 0.5
    assert metrics.refusal_rate == 0.5
    assert metrics.avg_response_time_ms == 150

    write_metrics_csv(metrics, metrics_path)
    assert metrics_path.exists()
