-- Add referential integrity — FK constraints with ON DELETE CASCADE for child tables so that
-- delete_hunt (and any out-of-band cleanup) propagates atomically.
--
-- Preamble: remove any orphaned child rows first. `apply_schema` ran CREATE IF NOT EXISTS
-- without FKs so orphans can exist. Adding a FK with orphaned rows would fail.
DELETE FROM events      WHERE hunt_id NOT IN (SELECT hunt_id FROM hunts);
DELETE FROM artifacts   WHERE hunt_id NOT IN (SELECT hunt_id FROM hunts);
DELETE FROM messages    WHERE hunt_id NOT IN (SELECT hunt_id FROM hunts);
DELETE FROM checkpoints WHERE hunt_id NOT IN (SELECT hunt_id FROM hunts);
DELETE FROM feedback    WHERE hunt_id NOT IN (SELECT hunt_id FROM hunts);

-- hunts → projects: NULL-safe (project_id is optional; NULL on orphan, not an error).
ALTER TABLE hunts ADD CONSTRAINT fk_hunts_project
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE SET NULL;

-- All child tables cascade on hunt delete.
ALTER TABLE events ADD CONSTRAINT fk_events_hunt
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id) ON DELETE CASCADE;

ALTER TABLE artifacts ADD CONSTRAINT fk_artifacts_hunt
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id) ON DELETE CASCADE;

ALTER TABLE messages ADD CONSTRAINT fk_messages_hunt
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id) ON DELETE CASCADE;

ALTER TABLE checkpoints ADD CONSTRAINT fk_checkpoints_hunt
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id) ON DELETE CASCADE;

ALTER TABLE feedback ADD CONSTRAINT fk_feedback_hunt
    FOREIGN KEY (hunt_id) REFERENCES hunts(hunt_id) ON DELETE CASCADE;
