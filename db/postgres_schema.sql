-- PostgreSQL schema for immutable nutrition/symptom tracking suitable for research export.
-- Assumes PostgreSQL 14+.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Generic trigger function to enforce append-only behavior.
CREATE OR REPLACE FUNCTION prevent_row_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Table % is immutable; % operations are not allowed', TG_TABLE_NAME, TG_OP;
END;
$$;

-- Minimal subject registry.
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_subject_id TEXT NOT NULL UNIQUE,
    cohort_label TEXT,
    timezone_name TEXT NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (external_subject_id <> ''),
    CHECK (timezone_name <> '')
);

-- Controlled vocabulary for symptom severity.
CREATE TABLE IF NOT EXISTS severity_scale (
    severity_code SMALLINT PRIMARY KEY,
    severity_label TEXT NOT NULL UNIQUE,
    severity_description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (severity_code BETWEEN 0 AND 10),
    CHECK (severity_label <> ''),
    CHECK (severity_description <> '')
);

INSERT INTO severity_scale (severity_code, severity_label, severity_description)
VALUES
    (0, 'none', 'No symptom burden.'),
    (1, 'minimal', 'Very mild impact, barely noticeable.'),
    (2, 'mild', 'Mild impact, no major activity limitation.'),
    (3, 'moderate', 'Moderate impact, some activity limitation.'),
    (4, 'high', 'High impact, clear activity limitation.'),
    (5, 'severe', 'Severe impact, major limitation or distress.')
ON CONFLICT (severity_code) DO NOTHING;

-- Immutable food consumption events.
CREATE TABLE IF NOT EXISTS food_entries (
    food_entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    consumed_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    meal_type TEXT,
    food_name TEXT NOT NULL,
    quantity_value NUMERIC(10,2),
    quantity_unit TEXT,
    preparation_notes TEXT,
    source_system TEXT NOT NULL DEFAULT 'telegram-bot',
    source_message_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (food_name <> ''),
    CHECK (source_system <> ''),
    CHECK (quantity_value IS NULL OR quantity_value >= 0)
);

-- Immutable symptom observations, optionally linked to food entries.
CREATE TABLE IF NOT EXISTS symptoms (
    symptom_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    observed_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    symptom_name TEXT NOT NULL,
    severity_code SMALLINT REFERENCES severity_scale(severity_code),
    symptom_notes TEXT,
    related_food_entry_id UUID REFERENCES food_entries(food_entry_id),
    source_system TEXT NOT NULL DEFAULT 'telegram-bot',
    source_message_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (symptom_name <> ''),
    CHECK (source_system <> '')
);

-- Indexes for analytics and research exports.
CREATE INDEX IF NOT EXISTS idx_food_entries_user_consumed_at
    ON food_entries (user_id, consumed_at);

CREATE INDEX IF NOT EXISTS idx_symptoms_user_observed_at
    ON symptoms (user_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_symptoms_related_food
    ON symptoms (related_food_entry_id)
    WHERE related_food_entry_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_food_entries_metadata_gin
    ON food_entries USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_symptoms_metadata_gin
    ON symptoms USING GIN (metadata);

-- Enforce immutability on all domain tables.
DROP TRIGGER IF EXISTS users_immutable ON users;
CREATE TRIGGER users_immutable
BEFORE UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION prevent_row_mutation();

DROP TRIGGER IF EXISTS severity_scale_immutable ON severity_scale;
CREATE TRIGGER severity_scale_immutable
BEFORE UPDATE OR DELETE ON severity_scale
FOR EACH ROW EXECUTE FUNCTION prevent_row_mutation();

DROP TRIGGER IF EXISTS food_entries_immutable ON food_entries;
CREATE TRIGGER food_entries_immutable
BEFORE UPDATE OR DELETE ON food_entries
FOR EACH ROW EXECUTE FUNCTION prevent_row_mutation();

DROP TRIGGER IF EXISTS symptoms_immutable ON symptoms;
CREATE TRIGGER symptoms_immutable
BEFORE UPDATE OR DELETE ON symptoms
FOR EACH ROW EXECUTE FUNCTION prevent_row_mutation();

-- Convenience research export view with explicit denormalized fields.
CREATE OR REPLACE VIEW research_export_v1 AS
SELECT
    s.symptom_id,
    s.user_id,
    u.external_subject_id,
    u.cohort_label,
    s.observed_at,
    s.recorded_at AS symptom_recorded_at,
    s.symptom_name,
    s.symptom_notes,
    s.severity_code,
    ss.severity_label,
    ss.severity_description,
    s.source_system AS symptom_source_system,
    s.source_message_id AS symptom_source_message_id,
    f.food_entry_id,
    f.consumed_at,
    f.recorded_at AS food_recorded_at,
    f.meal_type,
    f.food_name,
    f.quantity_value,
    f.quantity_unit,
    f.preparation_notes,
    f.source_system AS food_source_system,
    f.source_message_id AS food_source_message_id,
    s.metadata AS symptom_metadata,
    f.metadata AS food_metadata,
    u.metadata AS user_metadata
FROM symptoms s
JOIN users u ON u.user_id = s.user_id
LEFT JOIN severity_scale ss ON ss.severity_code = s.severity_code
LEFT JOIN food_entries f ON f.food_entry_id = s.related_food_entry_id;

COMMIT;
