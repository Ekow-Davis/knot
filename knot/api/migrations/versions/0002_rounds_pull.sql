-- Rounds: "ready" (everyone who needs to answer has sealed) and who has pulled their end.
-- Rounds are short-lived, so any existing rows are simply cleared.

DELETE FROM rounds;

ALTER TABLE rounds DROP CONSTRAINT round_state;
ALTER TABLE rounds ADD CONSTRAINT round_state CHECK (state IN ('open', 'ready'));

ALTER TABLE rounds ADD COLUMN pulled_by uuid[] NOT NULL DEFAULT '{}';

-- Only one live round at a time for the pair.
CREATE UNIQUE INDEX one_round_at_a_time ON rounds ((true));
