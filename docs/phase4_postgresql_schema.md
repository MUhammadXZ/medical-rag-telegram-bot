# Phase 4 PostgreSQL Schema Design (Deterministic Knowledge Layer)

## Goals
This schema introduces a **structured deterministic layer** alongside the existing FAISS-based RAG retrieval. It is designed to:

1. Store normalized medical knowledge entities and relationships.
2. Support deterministic rule evaluation before/alongside LLM generation.
3. Preserve full provenance/versioning for thesis reproducibility.
4. Integrate with existing emergency detection and food diary features.

---

## Logical domains

- **Identity & sessions**: users and chat sessions.
- **Medical ontology**: symptoms, conditions, medications, nutrients, and food items.
- **Deterministic knowledge graph edges**: condition-symptom, medication-condition, contraindications, interactions.
- **Rules engine layer**: rule definitions, versions, predicates, and execution logs.
- **Evidence/provenance**: source references and citation mapping.
- **Food diary facts**: meal logs, nutrient totals, medically relevant diet flags.
- **RAG bridge**: links from structured entities/rules to vector chunk identifiers.

---

## PostgreSQL DDL

```sql
-- Recommended extension for UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- ENUM TYPES ----------
CREATE TYPE severity_level AS ENUM ('low', 'moderate', 'high', 'critical');
CREATE TYPE evidence_level AS ENUM ('weak', 'moderate', 'strong', 'guideline');
CREATE TYPE rule_status AS ENUM ('draft', 'active', 'deprecated');
CREATE TYPE actor_type AS ENUM ('user', 'system', 'clinician', 'pipeline');
CREATE TYPE meal_type AS ENUM ('breakfast', 'lunch', 'dinner', 'snack', 'other');

-- ---------- USERS / SESSIONS ----------
CREATE TABLE app_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id TEXT UNIQUE NOT NULL,      -- e.g., Telegram user id
    locale TEXT,
    timezone TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'telegram',
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_chat_session_user_started ON chat_session(user_id, started_at DESC);

-- ---------- SOURCE / PROVENANCE ----------
CREATE TABLE source_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key TEXT UNIQUE NOT NULL,            -- canonical id in ingestion pipeline
    title TEXT NOT NULL,
    publisher TEXT,
    publication_date DATE,
    url TEXT,
    version_label TEXT,
    checksum_sha256 TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE source_excerpt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID NOT NULL REFERENCES source_document(id) ON DELETE CASCADE,
    excerpt_text TEXT NOT NULL,
    location_ref TEXT,                          -- page/section/table ref
    chunk_external_id TEXT,                     -- maps to FAISS/ingestion chunk id
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_source_excerpt_doc ON source_excerpt(source_document_id);
CREATE INDEX idx_source_excerpt_chunk_ext ON source_excerpt(chunk_external_id);

-- ---------- MEDICAL ONTOLOGY CORE ----------
CREATE TABLE medical_concept (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_type TEXT NOT NULL CHECK (concept_type IN (
        'symptom', 'condition', 'medication', 'allergen', 'nutrient', 'food_item', 'lab_marker'
    )),
    canonical_name TEXT NOT NULL,
    normalized_key TEXT NOT NULL,               -- lowercase slug for deterministic matching
    description TEXT,
    snomed_code TEXT,
    icd10_code TEXT,
    rxnorm_code TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (concept_type, normalized_key)
);

CREATE INDEX idx_medical_concept_type_key ON medical_concept(concept_type, normalized_key);
CREATE INDEX idx_medical_concept_codes ON medical_concept(snomed_code, icd10_code, rxnorm_code);

CREATE TABLE concept_synonym (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID NOT NULL REFERENCES medical_concept(id) ON DELETE CASCADE,
    synonym_text TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    language_code TEXT NOT NULL DEFAULT 'en',
    UNIQUE (concept_id, normalized_key, language_code)
);

CREATE INDEX idx_concept_synonym_norm ON concept_synonym(normalized_key, language_code);

-- ---------- DETERMINISTIC RELATIONSHIPS ----------
CREATE TABLE concept_relationship (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_concept_id UUID NOT NULL REFERENCES medical_concept(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL CHECK (predicate IN (
        'has_symptom',
        'suggests_condition',
        'treated_by_medication',
        'contraindicated_with_condition',
        'interacts_with_medication',
        'contains_nutrient',
        'avoid_in_allergy',
        'elevates_lab_marker',
        'reduces_lab_marker'
    )),
    object_concept_id UUID NOT NULL REFERENCES medical_concept(id) ON DELETE CASCADE,
    weight NUMERIC(5,4) NOT NULL DEFAULT 1.0,
    severity severity_level,
    evidence evidence_level NOT NULL DEFAULT 'moderate',
    is_directional BOOLEAN NOT NULL DEFAULT TRUE,
    source_excerpt_id UUID REFERENCES source_excerpt(id) ON DELETE SET NULL,
    effective_from DATE,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (subject_concept_id <> object_concept_id),
    UNIQUE (subject_concept_id, predicate, object_concept_id)
);

CREATE INDEX idx_rel_subject_pred ON concept_relationship(subject_concept_id, predicate);
CREATE INDEX idx_rel_object_pred ON concept_relationship(object_concept_id, predicate);

-- ---------- RULE ENGINE (DETERMINISTIC LAYER) ----------
CREATE TABLE rule_set (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,                  -- e.g., TRIAGE_CHEST_PAIN_V1
    name TEXT NOT NULL,
    description TEXT,
    status rule_status NOT NULL DEFAULT 'draft',
    priority INTEGER NOT NULL DEFAULT 100,      -- lower = evaluated earlier
    version INTEGER NOT NULL DEFAULT 1,
    created_by actor_type NOT NULL DEFAULT 'pipeline',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_rule_set_status_priority ON rule_set(status, priority, version DESC);

CREATE TABLE rule_clause (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_set_id UUID NOT NULL REFERENCES rule_set(id) ON DELETE CASCADE,
    clause_order INTEGER NOT NULL,
    clause_kind TEXT NOT NULL CHECK (clause_kind IN ('if', 'and', 'or', 'not', 'then')),
    left_operand_type TEXT NOT NULL CHECK (left_operand_type IN (
        'symptom', 'condition', 'medication', 'allergy', 'nutrient', 'food_item', 'vital_sign', 'age', 'free_text_flag'
    )),
    left_operand_value TEXT NOT NULL,
    operator TEXT NOT NULL CHECK (operator IN (
        '=', '!=', '>', '>=', '<', '<=', 'in', 'contains', 'exists', 'not_exists'
    )),
    right_operand_value TEXT,
    comparator_unit TEXT,
    confidence_floor NUMERIC(4,3),              -- optional threshold from extraction pipeline
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (rule_set_id, clause_order)
);

CREATE INDEX idx_rule_clause_rule_order ON rule_clause(rule_set_id, clause_order);
CREATE INDEX idx_rule_clause_left_operand ON rule_clause(left_operand_type, left_operand_value);

CREATE TABLE rule_action (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_set_id UUID NOT NULL REFERENCES rule_set(id) ON DELETE CASCADE,
    action_order INTEGER NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'raise_emergency_flag',
        'recommend_er',
        'recommend_clinician_followup',
        'recommend_food_adjustment',
        'block_medication_suggestion',
        'attach_explanation',
        'set_response_tone'
    )),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (rule_set_id, action_order)
);

CREATE INDEX idx_rule_action_rule_order ON rule_action(rule_set_id, action_order);

-- ---------- RULE EXECUTION TRACE ----------
CREATE TABLE rule_evaluation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_session(id) ON DELETE SET NULL,
    user_id UUID REFERENCES app_user(id) ON DELETE SET NULL,
    rule_set_id UUID NOT NULL REFERENCES rule_set(id) ON DELETE CASCADE,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    matched BOOLEAN NOT NULL,
    match_score NUMERIC(5,4),
    input_snapshot JSONB NOT NULL,              -- extracted deterministic facts at eval time
    matched_clauses JSONB NOT NULL DEFAULT '[]'::jsonb,
    triggered_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    latency_ms INTEGER,
    correlation_id TEXT
);

CREATE INDEX idx_rule_eval_user_time ON rule_evaluation_log(user_id, evaluated_at DESC);
CREATE INDEX idx_rule_eval_session_time ON rule_evaluation_log(session_id, evaluated_at DESC);
CREATE INDEX idx_rule_eval_rule_time ON rule_evaluation_log(rule_set_id, evaluated_at DESC);

-- ---------- USER FACT STORE ----------
CREATE TABLE user_medical_fact (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES medical_concept(id) ON DELETE CASCADE,
    fact_type TEXT NOT NULL CHECK (fact_type IN (
        'reported_symptom', 'diagnosed_condition', 'current_medication', 'allergy', 'dietary_preference'
    )),
    value_text TEXT,
    value_numeric NUMERIC(12,4),
    unit TEXT,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to TIMESTAMPTZ,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL DEFAULT 'chat',
    source_excerpt_id UUID REFERENCES source_excerpt(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE INDEX idx_user_fact_user_type ON user_medical_fact(user_id, fact_type, valid_from DESC);
CREATE INDEX idx_user_fact_concept ON user_medical_fact(concept_id);

-- ---------- FOOD DIARY EXTENSION ----------
CREATE TABLE food_diary_entry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    consumed_at TIMESTAMPTZ NOT NULL,
    meal meal_type NOT NULL DEFAULT 'other',
    free_text_input TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_food_entry_user_time ON food_diary_entry(user_id, consumed_at DESC);

CREATE TABLE food_diary_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id UUID NOT NULL REFERENCES food_diary_entry(id) ON DELETE CASCADE,
    food_concept_id UUID REFERENCES medical_concept(id) ON DELETE SET NULL,
    item_name_raw TEXT NOT NULL,
    quantity NUMERIC(12,3),
    quantity_unit TEXT,
    calories_kcal NUMERIC(10,2),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_food_item_entry ON food_diary_item(entry_id);
CREATE INDEX idx_food_item_food_concept ON food_diary_item(food_concept_id);

CREATE TABLE food_diary_item_nutrient (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    food_diary_item_id UUID NOT NULL REFERENCES food_diary_item(id) ON DELETE CASCADE,
    nutrient_concept_id UUID NOT NULL REFERENCES medical_concept(id) ON DELETE CASCADE,
    amount NUMERIC(12,4) NOT NULL,
    unit TEXT NOT NULL,
    UNIQUE (food_diary_item_id, nutrient_concept_id)
);

CREATE INDEX idx_food_item_nutrient_nutrient ON food_diary_item_nutrient(nutrient_concept_id);

-- ---------- RAG BRIDGE ----------
CREATE TABLE rag_entity_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID REFERENCES medical_concept(id) ON DELETE CASCADE,
    rule_set_id UUID REFERENCES rule_set(id) ON DELETE CASCADE,
    chunk_external_id TEXT NOT NULL,            -- FAISS-side chunk id
    link_strength NUMERIC(5,4) NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((concept_id IS NOT NULL) <> (rule_set_id IS NOT NULL))
);

CREATE INDEX idx_rag_entity_link_chunk ON rag_entity_link(chunk_external_id);
CREATE INDEX idx_rag_entity_link_concept ON rag_entity_link(concept_id);
CREATE INDEX idx_rag_entity_link_rule ON rag_entity_link(rule_set_id);

-- ---------- OPTIONAL: simple updated_at trigger ----------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON app_user
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_medical_concept_updated_at
BEFORE UPDATE ON medical_concept
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## Deterministic decision flow supported by this schema

1. **Ingestion/normalization** maps source text into `medical_concept`, `concept_synonym`, and `concept_relationship`.
2. User messages are converted to deterministic facts in `user_medical_fact`.
3. Active rules (`rule_set.status = 'active'`) are evaluated using `rule_clause` and produce `rule_action` output.
4. Every run is auditable in `rule_evaluation_log`.
5. Structured explanations can cite `source_excerpt` for transparent medical reasoning.
6. Existing vector retrieval remains primary for unstructured context; `rag_entity_link` binds entities/rules to FAISS chunks for hybrid retrieval.

---

## Recommended migration strategy

1. Create base tables: `app_user`, `chat_session`, source/provenance tables.
2. Introduce ontology tables and backfill from existing ingestion artifacts.
3. Add rules tables and migrate emergency rules first.
4. Extend food diary with nutrient decomposition.
5. Populate `rag_entity_link` for hybrid ranking.
6. Add nightly integrity checks (or DB tests) for orphaned references and duplicate normalized keys.

---

## Notes for thesis evaluation

- This design supports **reproducibility** (versioned rules + provenance).
- It enables **deterministic safety constraints** (contraindications/interactions before response synthesis).
- It supports **hybrid explainability** by linking symbolic facts to source excerpts and vector chunks.
