-- Pack — the durable data model (Doc 04 §5).
--
-- Postgres is the SINGLE SOURCE OF TRUTH. The engine writes here, in one transaction,
-- and nowhere else in the hot path. Redis is a pure projection, populated by the outbox
-- relay (app/engine/relay.py) tailing the `events` table. This is the transactional
-- outbox pattern: it removes the dual-write inconsistency window entirely.
--
-- Idempotent: safe to run on every boot (CREATE ... IF NOT EXISTS + additive ALTERs).

-- A hunt: one task the pack runs, start to finish.
CREATE TABLE IF NOT EXISTS hunts (
    hunt_id      TEXT PRIMARY KEY,
    state        TEXT        NOT NULL DEFAULT 'planning',
    source       TEXT        NOT NULL DEFAULT 'typed',   -- typed | spoken | dropped
    raw_input    TEXT,
    strategy     TEXT        NOT NULL DEFAULT 'orchestrate', -- orchestrate | deep_dive | critique
    boundary_usd DOUBLE PRECISION,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Older deployments may predate `strategy`; add it without disturbing existing rows.
ALTER TABLE hunts ADD COLUMN IF NOT EXISTS strategy TEXT NOT NULL DEFAULT 'orchestrate';

-- The event log. Append-only, never edited. This table IS the transactional outbox:
-- `relayed` marks whether the outbox relay has published the row to Redis yet.
-- PK (hunt_id, seq) is the real ordering backstop — it rejects any duplicate seq.
CREATE TABLE IF NOT EXISTS events (
    hunt_id  TEXT        NOT NULL,
    seq      INTEGER     NOT NULL,
    event_id TEXT        NOT NULL,
    ts       TEXT        NOT NULL,                       -- ISO-8601 UTC; stored verbatim
    type     TEXT        NOT NULL,
    actor    TEXT        NOT NULL,
    payload  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    relayed  BOOLEAN     NOT NULL DEFAULT FALSE,
    PRIMARY KEY (hunt_id, seq)
);

-- Older deployments may predate `relayed`; add it without disturbing existing rows.
ALTER TABLE events ADD COLUMN IF NOT EXISTS relayed BOOLEAN NOT NULL DEFAULT FALSE;

-- The relay scans only unpublished rows; a partial index keeps that scan cheap.
CREATE INDEX IF NOT EXISTS idx_events_unrelayed
    ON events (hunt_id, seq) WHERE relayed = FALSE;

-- Artifacts: drafts, the final brief, scorecards, transcripts.
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    hunt_id     TEXT        NOT NULL,
    kind        TEXT        NOT NULL,                    -- draft | final | scorecard | transcript
    produced_by TEXT,
    content     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Instincts: saved plan presets that survive across hunts (the Den).
CREATE TABLE IF NOT EXISTS instincts (
    instinct_id TEXT PRIMARY KEY,
    label       TEXT        NOT NULL,
    spec        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Checkpoints: written when the Boundary halts, so a hunt can resume (real logic NEXT).
CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    hunt_id       TEXT        NOT NULL,
    at_seq        INTEGER     NOT NULL,
    state         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
