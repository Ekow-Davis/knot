-- Knot: initial schema. Mirrors app/models.py — keep the two in step.
-- Run by migrations/versions/0001_initial.py. Postgres 13+ (gen_random_uuid is built in).

-- People ──────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         varchar(320) NOT NULL UNIQUE,
    display_name  varchar(40),
    spicy_on      boolean NOT NULL DEFAULT false,
    theme         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_lowercase CHECK (email = lower(email))
);

-- The knot itself: exactly one row, two seats.
CREATE TABLE pair (
    id                   smallint PRIMARY KEY DEFAULT 1,
    owner_id             uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    partner_id           uuid UNIQUE REFERENCES users(id) ON DELETE SET NULL,
    kdf_salt             bytea,
    kdf_params           jsonb,
    key_check            bytea,
    key_check_nonce      bytea,
    key_version          integer NOT NULL DEFAULT 0,
    settings             jsonb NOT NULL DEFAULT
        '{"depth": "light", "categories": ["cozy", "silly", "sweet"], "random": false, "excluded": []}'::jsonb,
    settings_updated_by  uuid REFERENCES users(id) ON DELETE SET NULL,
    settings_updated_at  timestamptz,
    turn_user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT single_pair CHECK (id = 1),
    CONSTRAINT two_different_people CHECK (partner_id IS NULL OR partner_id <> owner_id)
);

-- Sign-in ─────────────────────────────────────────────────────────────────────

CREATE TABLE email_codes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email        varchar(320) NOT NULL,
    code_hmac    varchar(64) NOT NULL,
    attempts     smallint NOT NULL DEFAULT 0,
    expires_at   timestamptz NOT NULL,
    consumed_at  timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_email_codes_email_created ON email_codes (email, created_at);

CREATE TABLE sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    varchar(64) NOT NULL UNIQUE,
    user_agent    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_used_at  timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL
);
CREATE INDEX ix_sessions_user_id ON sessions (user_id);

CREATE TABLE invites (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hmac   varchar(64) NOT NULL UNIQUE,
    created_by  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz,
    used_at     timestamptz,
    used_by     uuid REFERENCES users(id) ON DELETE SET NULL
);

-- Question bank ───────────────────────────────────────────────────────────────

CREATE TABLE question_packs (
    id              varchar(64) PRIMARY KEY,
    version         integer NOT NULL DEFAULT 1,
    checksum        varchar(64) NOT NULL,
    question_count  integer NOT NULL,
    imported_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id             varchar(64) PRIMARY KEY,
    pack_id        varchar(64) NOT NULL REFERENCES question_packs(id) ON DELETE RESTRICT,
    type           varchar(8) NOT NULL,
    depth          varchar(8) NOT NULL,
    category       varchar(24) NOT NULL,
    payload        bytea NOT NULL,
    payload_nonce  bytea NOT NULL,
    retired_at     timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT question_type CHECK (type IN ('guess', 'both', 'wyr', 'self')),
    CONSTRAINT question_depth CHECK (depth IN ('light', 'medium', 'deep'))
);
CREATE INDEX ix_questions_drawable ON questions (category, depth, type) WHERE retired_at IS NULL;

CREATE TABLE drawn_questions (
    question_id  varchar(64) PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
    drawn_at     timestamptz NOT NULL DEFAULT now()
);

-- Live play (rows deleted after every reveal) ─────────────────────────────────

CREATE TABLE rounds (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id  varchar(64) NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    drawn_by     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id   uuid REFERENCES users(id) ON DELETE CASCADE,
    state        varchar(10) NOT NULL DEFAULT 'open',
    passed_by    uuid REFERENCES users(id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    CONSTRAINT round_state CHECK (state IN ('open', 'revealed', 'verdict'))
);
CREATE INDEX ix_rounds_expires_at ON rounds (expires_at);

CREATE TABLE sealed_answers (
    round_id     uuid NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ciphertext   bytea NOT NULL,
    nonce        bytea NOT NULL,
    key_version  integer NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (round_id, user_id)
);

-- Push ────────────────────────────────────────────────────────────────────────

CREATE TABLE push_subscriptions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint    text NOT NULL UNIQUE,
    p256dh      text NOT NULL,
    auth        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_push_subscriptions_user_id ON push_subscriptions (user_id);
