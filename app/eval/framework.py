from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from app.data.retrieval import retrieve_chunks


@dataclass(frozen=True)
class GoldQuestion:
    question: str
    expected_keywords: tuple[str, ...]
    expected_section: str


@dataclass(frozen=True)
class EvaluationMetrics:
    total_questions: int
    retrieval_accuracy_topk: float
    retrieval_accuracy_top1: float
    refusal_rate: float
    avg_response_time_ms: float
    p95_response_time_ms: float


def load_gold_questions(csv_path: str | Path) -> list[GoldQuestion]:
    path = Path(csv_path)
    questions: list[GoldQuestion] = []

    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            keywords = tuple(
                keyword.strip().lower()
                for keyword in row["expected_keywords"].split(",")
                if keyword.strip()
            )
            questions.append(
                GoldQuestion(
                    question=row["question"].strip(),
                    expected_keywords=keywords,
                    expected_section=row["expected_section"].strip().lower(),
                )
            )

    return questions


def evaluate_retrieval(
    gold_questions: list[GoldQuestion],
    index: object,
    metadata: dict[str, object],
    *,
    embedding_model: str,
    embedding_client: object,
    top_k: int,
    min_similarity: float,
) -> EvaluationMetrics:
    if not gold_questions:
        raise ValueError("gold_questions must not be empty.")

    topk_hits = 0
    top1_hits = 0
    refusal_count = 0
    response_times_ms: list[float] = []

    for case in gold_questions:
        started_at = time.perf_counter()
        retrieval_result = retrieve_chunks(
            query=case.question,
            index=index,
            metadata=metadata,
            embedding_model=embedding_model,
            embedding_client=embedding_client,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        response_times_ms.append(elapsed_ms)

        refused = bool(retrieval_result["rejected"])
        if refused:
            refusal_count += 1
            continue

        retrieved = retrieval_result.get("retrieved", [])
        matched = [item for item in retrieved if _chunk_matches(case, item)]
        if matched:
            topk_hits += 1

        if retrieved and _chunk_matches(case, retrieved[0]):
            top1_hits += 1

    sorted_times = sorted(response_times_ms)
    p95_index = max(int(0.95 * len(sorted_times)) - 1, 0)

    total = len(gold_questions)
    return EvaluationMetrics(
        total_questions=total,
        retrieval_accuracy_topk=topk_hits / total,
        retrieval_accuracy_top1=top1_hits / total,
        refusal_rate=refusal_count / total,
        avg_response_time_ms=mean(response_times_ms),
        p95_response_time_ms=sorted_times[p95_index],
    )


def _chunk_matches(case: GoldQuestion, retrieved_item: dict[str, object]) -> bool:
    text = str(retrieved_item.get("text", "")).lower()
    metadata = retrieved_item.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    section = str(metadata.get("section", "")).lower()
    source = str(metadata.get("source", "")).lower()

    haystack = " ".join([text, section, source])

    section_hit = _section_matches(case.expected_section, haystack)
    keyword_hit = any(keyword in haystack for keyword in case.expected_keywords)
    return section_hit and keyword_hit


def _section_matches(expected_section: str, haystack: str) -> bool:
    section_aliases = {
        "definition": ["تعريف", "cmpa", "lactose"],
        "ingredients": ["casein", "whey", "مكونات", "ملصق"],
        "alternatives": ["بدائل", "حليب", "تركيبة", "soy", "oat"],
        "diagnosis": ["تشخيص", "ige", "اختبارات", "التاريخ"],
        "management": ["إدارة", "تجنب", "نمو", "متابعة"],
        "red_flags": ["علامات حمراء", "تأق", "إسعاف", "anaphylaxis"],
        "symptom_checker": ["rule", "تصنيف", "خفيف", "متوسط", "شديد"],
        "food_diary": ["يومية", "food diary", "التاريخ", "الوجبة"],
        "recipes": ["الوصفة", "مكونات", "التحضير", "ملاءمة العمر"],
        "medical_recommendations": ["wao", "aaaai", "تحدي غذائي", "إحالة"],
    }
    aliases = section_aliases.get(expected_section, [expected_section])
    return any(alias.lower() in haystack for alias in aliases)


def write_metrics_csv(metrics: EvaluationMetrics, output_csv_path: str | Path) -> None:
    path = Path(output_csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_questions", metrics.total_questions])
        writer.writerow(["retrieval_accuracy_topk", f"{metrics.retrieval_accuracy_topk:.4f}"])
        writer.writerow(["retrieval_accuracy_top1", f"{metrics.retrieval_accuracy_top1:.4f}"])
        writer.writerow(["refusal_rate", f"{metrics.refusal_rate:.4f}"])
        writer.writerow(["avg_response_time_ms", f"{metrics.avg_response_time_ms:.2f}"])
        writer.writerow(["p95_response_time_ms", f"{metrics.p95_response_time_ms:.2f}"])
