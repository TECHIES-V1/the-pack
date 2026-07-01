-- Composite index for the (created_at DESC, hunt_id DESC) cursor pagination introduced in
-- list_hunts. Without this, every page-2+ request is a full seqscan of the hunts table.
CREATE INDEX IF NOT EXISTS idx_hunts_cursor
    ON hunts (created_at DESC, hunt_id DESC)
    WHERE archived = FALSE;
