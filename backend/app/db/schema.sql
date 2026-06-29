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

-- History management + sharing: a user-editable title, an archive flag, a project grouping, and a
-- public share token. All additive so existing rows are untouched.
ALTER TABLE hunts ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE hunts ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE hunts ADD COLUMN IF NOT EXISTS project_id TEXT;
ALTER TABLE hunts ADD COLUMN IF NOT EXISTS share_token TEXT;

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

-- Conversation with Alpha, per hunt — so reopening a hunt restores its real chat (cross-device,
-- not just this browser's localStorage).
CREATE TABLE IF NOT EXISTS messages (
    hunt_id    TEXT        NOT NULL,
    seq        INTEGER     NOT NULL,
    role       TEXT        NOT NULL,                     -- user | alpha
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hunt_id, seq)
);

-- Projects: a named workspace that groups hunts (+ shared instructions).
CREATE TABLE IF NOT EXISTS projects (
    project_id   TEXT PRIMARY KEY,
    label        TEXT        NOT NULL,
    instructions TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Instincts: saved plan presets that survive across hunts (the Den).
CREATE TABLE IF NOT EXISTS instincts (
    instinct_id TEXT PRIMARY KEY,
    label       TEXT        NOT NULL,
    spec        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Memory (v2): what the pack learned across hunts. Local-only, no accounts. The Elder reads recent
-- entries to seed planning and writes a takeaway when a hunt finishes.
CREATE TABLE IF NOT EXISTS memory (
    id         BIGSERIAL   PRIMARY KEY,
    hunt_id    TEXT,
    kind       TEXT        NOT NULL DEFAULT 'takeaway',
    text       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Knowledge base (v4.2): your own documents, local-only. Parsed to text on upload and injected into
-- a hunt's research as sources (alongside the web). No object store — the text is what's researched.
CREATE TABLE IF NOT EXISTS documents (
    id         BIGSERIAL   PRIMARY KEY,
    name       TEXT        NOT NULL,
    kind       TEXT        NOT NULL DEFAULT 'text',
    text       TEXT        NOT NULL,
    chars      INTEGER     NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Feedback: thumbs up/down votes on Alpha replies (turn_index matches the chatStore turn array).
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    hunt_id     TEXT        NOT NULL,
    turn_index  INT         NOT NULL,
    vote        TEXT        NOT NULL CHECK (vote IN ('up', 'down')),
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

-- Read-path indexes (additive). The (hunt_id, seq) PK already covers event replay; these speed the
-- per-hunt list/download queries, the Den's recency sort, and the /spend hunt_completed scan.
CREATE INDEX IF NOT EXISTS idx_artifacts_hunt    ON artifacts (hunt_id, kind);
CREATE INDEX IF NOT EXISTS idx_messages_hunt     ON messages (hunt_id);
CREATE INDEX IF NOT EXISTS idx_hunts_recent      ON hunts (created_at DESC) WHERE archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_hunts_project     ON hunts (project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_hunt  ON checkpoints (hunt_id, at_seq DESC);
-- /spend reads only the terminal totals event per hunt — a partial index keeps that scan tiny.
CREATE INDEX IF NOT EXISTS idx_events_completed  ON events (hunt_id, seq DESC) WHERE type = 'hunt_completed';
