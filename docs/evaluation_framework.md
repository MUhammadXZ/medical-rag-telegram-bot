# Evaluation Framework for Medical RAG Responses

This framework evaluates 50 manually labeled test questions and reports metrics in CSV format.

## Assets

- Gold set: `eval/gold_questions.csv`
  - Contains 50 test questions.
  - Contains manually written gold answers.
  - Contains expected gold chunk IDs for retrieval checks.
- Predictions template: `eval/predictions_template.csv`
  - Copy to `eval/predictions.csv` and populate with model outputs.
- Evaluator script: `scripts/run_eval.py`
- Metrics implementation: `app/eval/framework.py`

## Metrics computed

1. `retrieval_accuracy_topk`
   - Fraction of questions where **any** retrieved chunk ID matches the gold chunk IDs.
2. `retrieval_accuracy_top1`
   - Fraction where the **first** retrieved chunk matches a gold chunk ID.
3. `hallucination_rate`
   - Fraction of questions marked as hallucinated in the predictions file.
4. `refusal_rate`
   - Fraction of questions where the assistant refused.
5. `avg_response_time_ms`
   - Mean response latency in milliseconds.
6. `p95_response_time_ms`
   - 95th percentile response latency in milliseconds.

## How to run

1. Create prediction file:

```bash
cp eval/predictions_template.csv eval/predictions.csv
```

2. Fill each row with:

- `generated_answer`: assistant output text.
- `retrieved_chunk_ids`: semicolon-separated IDs in retrieval order.
- `refused`: `true` or `false`.
- `hallucinated`: `true` or `false` (manual or judge-model labeling).
- `response_time_ms`: numeric latency.

3. Execute:

```bash
python scripts/run_eval.py --gold eval/gold_questions.csv --predictions eval/predictions.csv --output eval/metrics.csv
```

4. Read metrics at `eval/metrics.csv`.
