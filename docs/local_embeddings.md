# Local embeddings (no OpenAI key)

The ingestion/retrieval pipeline supports an OpenAI-compatible embedding client interface.

## Default behavior

- If `OPENAI_API_KEY` is set and the `openai` package is available, the pipeline uses OpenAI embeddings.
- If `OPENAI_API_KEY` is missing, it falls back to local `sentence-transformers` embeddings when available.

## Force local embeddings

Use a `local:` prefix in `embedding_model`:

- `local:sentence-transformers/all-MiniLM-L6-v2`
- `local:BAAI/bge-small-en-v1.5`
- `local:intfloat/e5-small-v2`

Example:

```python
rebuild_index(
    source_path="cmpa_knowledge.txt",
    output_dir="artifacts",
    embedding_model="local:BAAI/bge-small-en-v1.5",
)
```

Install dependency:

```bash
pip install sentence-transformers
```
