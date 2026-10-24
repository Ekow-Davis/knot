-- Sealed questions can queue up for someone who's away, so more than one round may be live.
DROP INDEX IF EXISTS one_round_at_a_time;

-- Who has already read the answers on their phone (pulled while the other was away).
-- Their phone stops showing that round; it stays until the other person pulls or it expires.
ALTER TABLE rounds ADD COLUMN read_by uuid[] NOT NULL DEFAULT '{}';
