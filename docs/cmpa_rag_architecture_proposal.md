# CMPA Medical Thesis Chatbot — Production RAG Architecture (Design Proposal)

## 1) Proposed Folder Structure

```text
medical-rag-telegram-bot/
├─ app/
│  ├─ main.py                         # FastAPI entrypoint
│  ├─ api/
│  │  ├─ routes_chat.py               # /chat endpoint
│  │  ├─ routes_admin.py              # thresholds/config/admin diagnostics
│  │  └─ schemas.py                   # Pydantic request/response models
│  ├─ core/
│  │  ├─ config.py                    # environment + runtime config
│  │  ├─ logging.py                   # structured logging setup
│  │  ├─ security.py                  # auth, rate limiting hooks
│  │  └─ exceptions.py                # domain-specific exceptions
│  ├─ rag/
│  │  ├─ pipeline.py                  # orchestration of retrieval + answer flow
│  │  ├─ retriever.py                 # FAISS retrieval + threshold filtering
│  │  ├─ reranker.py                  # optional cross-encoder reranking
│  │  ├─ context_builder.py           # prompt context assembly from chunks
│  │  ├─ grounding_guard.py           # strict grounding + refusal checks
│  │  ├─ citation_guard.py            # citation completeness/format enforcement
│  │  ├─ hallucination_guard.py       # unsupported-claim detection
│  │  ├─ response_validator.py        # final QA gates before returning
│  │  └─ models.py                    # internal dataclasses for chunks/scores
│  ├─ llm/
│  │  ├─ client.py                    # LLM provider abstraction
│  │  ├─ prompt_templates.py          # system/task templates with constraints
│  │  └─ output_parser.py             # parse + normalize model outputs
│  ├─ data/
│  │  ├─ ingestion/
│  │  │  ├─ loaders.py                # PDF/Docx/Markdown thesis source loaders
│  │  │  ├─ chunker.py                # medical-safe chunking strategy
│  │  │  ├─ metadata_enricher.py      # source/page/section attribution
│  │  │  ├─ embedding.py              # embedding generation interface
│  │  │  └─ index_builder.py          # FAISS index creation/update
│  │  └─ stores/
│  │     ├─ faiss_index/              # persisted FAISS artifacts
│  │     └─ docstore/                 # source chunks + metadata mapping
│  ├─ observability/
│  │  ├─ audit_logger.py              # retrieval logs (chunks + scores)
│  │  ├─ metrics.py                   # latency, refusal rate, hit-rate
│  │  └─ tracing.py                   # OpenTelemetry spans (optional)
│  └─ tests/
│     ├─ unit/
│     ├─ integration/
│     └─ eval/
│        ├─ grounding_eval_cases.json
│        ├─ citation_eval_cases.json
│        └─ hallucination_eval_cases.json
├─ scripts/
│  ├─ ingest_corpus.py                # build/update vector index
│  ├─ run_eval.py                     # offline eval pipeline
│  └─ export_retrieval_logs.py        # audit export for thesis appendix
├─ configs/
│  ├─ app.yaml                        # env-neutral defaults
│  ├─ thresholds.yaml                 # similarity/refusal/citation thresholds
│  └─ prompts.yaml                    # versioned prompt variants
├─ docs/
│  ├─ architecture.md                 # system architecture narrative
│  ├─ data_governance.md              # privacy + dataset provenance
│  ├─ clinical_safety_policy.md       # non-diagnostic behavior + disclaimers
│  └─ cmpa_rag_architecture_proposal.md
├─ docker/
│  ├─ Dockerfile
│  └─ docker-compose.yml
├─ .env.example
├─ pyproject.toml
└─ README.md
```

---

## 2) Data Flow Diagram (Textual)

1. **User Query Ingress (FastAPI `/chat`)**
   - Request arrives with `query`, user/session metadata, and optional mode flags.
   - Input validation + sanitization executed.

2. **Pre-Retrieval Guardrail Layer**
   - Query intent classification (academic CMPA scope vs out-of-scope).
   - If out-of-scope or unsafe, return controlled refusal template.

3. **Embedding + Retrieval (FAISS)**
   - Query embedding computed.
   - FAISS top-`k` nearest chunks retrieved.
   - Each chunk returned with metadata: `source_id`, `title`, `page`, `section`, `chunk_id`, `similarity_score`.

4. **Similarity Threshold Control**
   - Apply configurable minimum similarity threshold.
   - Drop chunks below threshold.
   - If no chunks remain, trigger “insufficient evidence” refusal.

5. **Optional Re-ranking Stage**
   - Re-rank retained chunks with cross-encoder (if enabled).
   - Keep top `n` evidence chunks for prompt context.

6. **Grounded Context Builder**
   - Construct constrained context block strictly from retrieved chunks.
   - Include machine-readable citation map for each chunk.

7. **Constrained LLM Generation**
   - Prompt enforces: “Use only provided context, cite every factual claim, otherwise refuse.”
   - LLM generates structured answer draft with inline citation placeholders.

8. **Post-Generation Validation Gates**
   - **Citation Guard:** verifies every factual statement is linked to at least one retrieved chunk.
   - **Grounding/Hallucination Guard:** checks answer claims against retrieved evidence.
   - If validation fails, transform into safe refusal / partial-answer fallback.

9. **Response Egress**
   - Return answer + formatted citations + confidence/status metadata.
   - Include refusal reason when relevant (e.g., low evidence score).

10. **Audit & Observability**
   - Log retrieved chunk IDs, raw similarity scores, threshold used, accepted/rejected chunks, refusal reason, and latency.
   - Emit metrics for monitoring (retrieval hit rate, refusal frequency, citation pass rate).

---

## 3) Why These Choices Fit a Medical Academic Project

### A. Strict Context Grounding
- Medical and thesis contexts require traceability to source evidence; grounding ensures statements are anchored to specific CMPA materials rather than model prior knowledge.
- This supports academic defensibility and reduces clinical misinformation risk.

### B. Citation Enforcement
- Mandatory citations align with scholarly writing standards and allows supervisors/examiners to verify each claim quickly.
- Inline linkage to `source/page/section` makes the chatbot useful as a research tool, not just a generic Q&A bot.

### C. Hallucination Refusal Mechanism
- In medicine, confident but unsupported statements are high risk.
- A refusal policy (“insufficient evidence in indexed corpus”) is safer and academically honest than speculative generation.

### D. Similarity Threshold Control
- Thresholds prevent weakly related chunks from polluting context and causing subtle errors.
- Config-driven thresholds allow empirical tuning during evaluation for best precision/recall tradeoff per thesis corpus.

### E. Logging Retrieved Chunks + Similarity Scores
- Audit logs are crucial for reproducibility and thesis methodology sections.
- Enables post-hoc error analysis: why an answer was produced, why refusal triggered, and which retrieval stage failed.

### F. Modular Architecture
- Separation of retrieval, validation, and generation allows independent testing, replacement, and regulatory review.
- Medical projects evolve (new papers/guidelines), so modularity supports safer maintenance and version-controlled changes.

### G. FAISS Vector Store
- FAISS offers fast approximate nearest-neighbor search for local/private deployments and large thesis corpora.
- It is reliable, well-documented, and suitable for controlled academic infrastructure without mandatory external SaaS dependencies.

### H. FastAPI Backend
- FastAPI provides typed contracts, automatic OpenAPI docs, and robust async performance for chat workloads.
- Clean API boundaries make it easy to integrate Telegram, web frontends, and evaluation tooling.

### I. Evaluation-First + Governance Docs
- Dedicated eval suites (grounding/citation/hallucination) transform safety goals into measurable quality gates.
- Governance docs (data provenance, clinical safety policy) are especially important in medical domains where trust and compliance matter.
