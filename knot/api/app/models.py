"""Database tables. See docs/ARCHITECTURE.md §8 for the why behind each one.

Rule of thumb: the server only ever stores ciphertext for anything either person writes.
Readable columns are limited to what the server needs to route, filter and expire things.
"""

import json
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

QUESTION_TYPES = ("guess", "both", "wyr", "self")
DEPTHS = ("light", "medium", "deep")
CATEGORIES = ("cozy", "silly", "sweet", "spicy", "big", "memories", "future")
ROUND_STATES = ("open", "revealed", "verdict")

DEFAULT_SETTINGS = {
    "depth": "light",
    "categories": ["cozy", "silly", "sweet"],
    "random": False,
    "excluded": [],
}


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── People ────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)  # stored lower-case
    display_name: Mapped[str | None] = mapped_column(String(40))
    spicy_on: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    # {"mode": "night"|"candle", "preset": "plum", "base_hue": 340, "accent_hue": 38}
    theme: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)


class Pair(Base):
    """The knot itself. Exactly one row ever exists (id = 1), with two seats."""

    __tablename__ = "pair"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    partner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )

    # Passphrase: the server holds the salt and a check value, never the phrase or the key.
    kdf_salt: Mapped[bytes | None] = mapped_column(LargeBinary)
    kdf_params: Mapped[dict | None] = mapped_column(JSONB)  # {"alg": "argon2id", "m": 65536, "t": 3, "p": 1}
    key_check: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_check_nonce: Mapped[bytes | None] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)

    # Shared, live settings (depth, categories, random, excluded).
    settings: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text(f"'{json.dumps(DEFAULT_SETTINGS)}'::jsonb"),
        nullable=False,
    )
    settings_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    settings_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turn_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        CheckConstraint("id = 1", name="single_pair"),
        CheckConstraint("partner_id IS NULL OR partner_id <> owner_id", name="two_different_people"),
    )


# ── Sign-in ───────────────────────────────────────────────────────────────────


class EmailCode(Base):
    __tablename__ = "email_codes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    code_hmac: Mapped[str] = mapped_column(String(64), nullable=False)  # hex HMAC-SHA256, never the code
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()

    __table_args__ = (Index("ix_email_codes_email_created", "email", "created_at"),)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # sha256 of cookie token
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()
    last_used_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Invite(Base):
    """A one-time pairing code (TIE-XXXX). Only its HMAC is stored."""

    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = _uuid_pk()
    code_hmac: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


# ── Question bank ─────────────────────────────────────────────────────────────


class QuestionPack(Base):
    __tablename__ = "question_packs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "silly-002"
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of the encrypted pack file
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = _now()


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # permanent, e.g. "silly-002-0017"
    pack_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("question_packs.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(8), nullable=False)
    depth: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    # AES-GCM(BANK_KEY) of {"q": "...", "options": [...]} — readable only at draw time.
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        CheckConstraint(_in("type", QUESTION_TYPES), name="question_type"),
        CheckConstraint(_in("depth", DEPTHS), name="question_depth"),
        # Category is validated in the app, not here, so a new category never needs a migration.
        Index(
            "ix_questions_drawable",
            "category",
            "depth",
            "type",
            postgresql_where=text("retired_at IS NULL"),
        ),
    )


class DrawnQuestion(Base):
    """The 'already played' list. Question IDs only — never answers."""

    __tablename__ = "drawn_questions"

    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    drawn_at: Mapped[datetime] = _now()


# ── Live play (deleted after every reveal) ───────────────────────────────────


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[uuid.UUID] = _uuid_pk()
    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    drawn_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # For Guess: the person being guessed about (they give the verdict).
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(10), server_default=text("'open'"), nullable=False)
    passed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (CheckConstraint(_in("state", ROUND_STATES), name="round_state"),)


class SealedAnswer(Base):
    __tablename__ = "sealed_answers"

    round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (PrimaryKeyConstraint("round_id", "user_id"),)


# ── Push ──────────────────────────────────────────────────────────────────────


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()
