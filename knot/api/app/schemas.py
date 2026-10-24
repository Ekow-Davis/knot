"""Request and response shapes."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


def _clean_name(v: str) -> str:
    v = " ".join(v.split())  # collapse whitespace
    if not v:
        raise ValueError("Name can't be empty")
    return v


# ── Auth ──────────────────────────────────────────────────────────────────────


class CodeRequest(BaseModel):
    email: EmailStr


class CodeRequested(BaseModel):
    ok: bool = True
    resend_after: int


class VerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class InviteCheck(BaseModel):
    ticket: str
    invite_code: str = Field(min_length=4, max_length=20)


class JoinRequest(BaseModel):
    ticket: str
    display_name: str = Field(min_length=1, max_length=40)
    invite_code: str | None = Field(default=None, max_length=20)

    @field_validator("display_name")
    @classmethod
    def _n(cls, v: str) -> str:
        return _clean_name(v)


# ── People ────────────────────────────────────────────────────────────────────


class ThemeIn(BaseModel):
    mode: Literal["night", "candle"]
    preset: str = Field(max_length=16)
    base_hue: int = Field(ge=0, le=360)
    accent_hue: int = Field(ge=0, le=360)


class MeUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    theme: ThemeIn | None = None

    @field_validator("display_name")
    @classmethod
    def _n(cls, v: str | None) -> str | None:
        return None if v is None else _clean_name(v)


class PersonOut(BaseModel):
    id: uuid.UUID
    display_name: str | None
    theme: dict


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    theme: dict
    spicy_on: bool
    role: Literal["owner", "partner"]
    pair_complete: bool
    partner: PersonOut | None


class VerifyResult(BaseModel):
    """What happens after a correct code:
    signed_in      → existing account, session cookie set, `me` filled
    new_owner      → OWNER_EMAIL with no pair yet: go to the name step (no pairing code)
    needs_pairing  → new person: go to the pairing-code step
    """

    status: Literal["signed_in", "new_owner", "needs_pairing"]
    ticket: str | None = None
    me: MeOut | None = None


# ── Invites ───────────────────────────────────────────────────────────────────


class InviteOut(BaseModel):
    code: str
    expires_at: datetime


class InviteStatus(BaseModel):
    pair_complete: bool
    pending_invite_expires_at: datetime | None
