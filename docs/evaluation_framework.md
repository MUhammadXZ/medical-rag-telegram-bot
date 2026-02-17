# Evaluation Framework for CMPA Retrieval Quality

This framework evaluates the CMPA gold set and reports retrieval metrics using a real FAISS index built from the project CMPA sources.

## Assets

- Gold set: `eval/gold_questions_cmpa.csv`
  - Contains realistic Arabic and English CMPA user questions.
  - Contains expected retrieval keywords per question.
  - Contains expected section labels (for semantic matching).
- Evaluator script: `scripts/run_eval.py`
- Metrics implementation: `app/eval/framework.py`

## Metrics computed

1. `retrieval_accuracy_topk`
   - Fraction of questions where any of the top-k retrieved chunks matches both expected section and expected keywords.
2. `retrieval_accuracy_top1`
   - Fraction where the first retrieved chunk matches expected section and expected keywords.
3. `refusal_rate`
   - Fraction of questions where retrieval confidence is below `min_similarity` and the system rejects answering.
4. `avg_response_time_ms`
   - Mean measured retrieval latency in milliseconds.
5. `p95_response_time_ms`
   - Measured 95th percentile retrieval latency in milliseconds.

## How to run

```bash
python scripts/run_eval.py --gold eval/gold_questions_cmpa.csv --output eval/metrics.csv --index-dir eval/faiss --top-k 5 --min-similarity 0.15
```

The script:

1. Ingests only:
   - `cmpa_knowledge.txt`
   - `medical_guidelines_summary.txt`
   - `symptom_checker_logic.txt`
   - `recipes_database.txt`
2. Builds a FAISS index and metadata under `eval/faiss`.
3. Runs retrieval for every gold question.
4. Writes aggregate metrics to `eval/metrics.csv`.
