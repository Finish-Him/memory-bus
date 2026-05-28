-- Memory Bus: Initial schema + 4 agent schemas
-- Run this on the KVM2 Supabase Postgres

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schemas for each agent
CREATE SCHEMA IF NOT EXISTS atlas;
CREATE SCHEMA IF NOT EXISTS zeus;
CREATE SCHEMA IF NOT EXISTS alexandria;
CREATE SCHEMA IF NOT EXISTS arquimedes;

-- Common ingest_runs table for each schema
DO $$
DECLARE
    schemas TEXT[] := ARRAY['atlas', 'zeus', 'alexandria', 'arquimedes'];
    s TEXT;
BEGIN
    FOREACH s IN ARRAY schemas LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.ingest_runs (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                status text NOT NULL CHECK (status IN (''running'', ''completed'', ''failed'')),
                started_at timestamptz NOT NULL DEFAULT now(),
                finished_at timestamptz,
                documents_count integer NOT NULL DEFAULT 0,
                chunks_count integer NOT NULL DEFAULT 0,
                embedded_count integer NOT NULL DEFAULT 0,
                blocked_count integer NOT NULL DEFAULT 0,
                error text
            )
        ', s);
    END LOOP;
END $$;
