from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


@dataclass(frozen=True)
class GoldCase:
    question_id: str
    question: str
    gold_answer: str
    gold_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class Prediction:
    question_id: str
    generated_answer: str
    retrieved_chunk_ids: tuple[str, ...]
    refused: bool
    hallucinated: bool
    response_time_ms: float


@dataclass(frozen=True)
class EvaluationMetrics:
    total_questions: int
    retrieval_accuracy_topk: float
    retrieval_accuracy_top1: float
    hallucination_rate: float
    refusal_rate: float
    avg_response_time_ms: float
    p95_response_time_ms: float


def load_gold_cases(csv_path: str | Path) -> dict[str, GoldCase]:
    path = Path(csv_path)
    rows: dict[str, GoldCase] = {}
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            question_id = row["question_id"].strip()
            chunk_ids = tuple(
                chunk.strip() for chunk in row["gold_chunk_ids"].split(";") if chunk.strip()
            )
            rows[question_id] = GoldCase(
                question_id=question_id,
                question=row["question"].strip(),
                gold_answer=row["gold_answer"].strip(),
                gold_chunk_ids=chunk_ids,
            )
    return rows


def load_predictions(csv_path: str | Path) -> dict[str, Prediction]:
    path = Path(csv_path)
    rows: dict[str, Prediction] = {}
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            question_id = row["question_id"].strip()
            chunk_ids = tuple(
                chunk.strip() for chunk in row["retrieved_chunk_ids"].split(";") if chunk.strip()
            )
            rows[question_id] = Prediction(
                question_id=question_id,
                generated_answer=row["generated_answer"].strip(),
                retrieved_chunk_ids=chunk_ids,
                refused=row["refused"].strip().lower() == "true",
                hallucinated=row["hallucinated"].strip().lower() == "true",
                response_time_ms=float(row["response_time_ms"]),
            )
    return rows


def evaluate(gold_cases: dict[str, GoldCase], predictions: dict[str, Prediction]) -> EvaluationMetrics:
    missing_predictions = sorted(set(gold_cases) - set(predictions))
    if missing_predictions:
        raise ValueError(
            "Missing predictions for question IDs: " + ", ".join(missing_predictions)
        )

    total = len(gold_cases)
    topk_hits = 0
    top1_hits = 0
    refusal_count = 0
    hallucination_count = 0
    response_times: list[float] = []

    for question_id, gold_case in gold_cases.items():
        prediction = predictions[question_id]

        response_times.append(prediction.response_time_ms)
        if prediction.refused:
            refusal_count += 1
        if prediction.hallucinated:
            hallucination_count += 1

        gold_chunks = set(gold_case.gold_chunk_ids)
        retrieved_chunks = prediction.retrieved_chunk_ids

        if any(chunk_id in gold_chunks for chunk_id in retrieved_chunks):
            topk_hits += 1

        if retrieved_chunks and retrieved_chunks[0] in gold_chunks:
            top1_hits += 1

    sorted_times = sorted(response_times)
    p95_index = max(int(0.95 * len(sorted_times)) - 1, 0)

    return EvaluationMetrics(
        total_questions=total,
        retrieval_accuracy_topk=topk_hits / total,
        retrieval_accuracy_top1=top1_hits / total,
        hallucination_rate=hallucination_count / total,
        refusal_rate=refusal_count / total,
        avg_response_time_ms=mean(response_times),
        p95_response_time_ms=sorted_times[p95_index],
    )


def write_metrics_csv(metrics: EvaluationMetrics, output_csv_path: str | Path) -> None:
    path = Path(output_csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_questions", metrics.total_questions])
        writer.writerow(["retrieval_accuracy_topk", f"{metrics.retrieval_accuracy_topk:.4f}"])
        writer.writerow(["retrieval_accuracy_top1", f"{metrics.retrieval_accuracy_top1:.4f}"])
        writer.writerow(["hallucination_rate", f"{metrics.hallucination_rate:.4f}"])
        writer.writerow(["refusal_rate", f"{metrics.refusal_rate:.4f}"])
        writer.writerow(["avg_response_time_ms", f"{metrics.avg_response_time_ms:.2f}"])
        writer.writerow(["p95_response_time_ms", f"{metrics.p95_response_time_ms:.2f}"])
