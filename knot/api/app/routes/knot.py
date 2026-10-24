"""The knot: what the server keeps so both phones can derive the same key from the shared phrase.

The server never sees the phrase or the key. It holds:
  • the Argon2id salt and settings (so both phones derive the same key)
  • a "key check": a fixed string encrypted with the key, so a phone can tell
    "wrong phrase" apart from "right phrase" without the server knowing either
  • key_version, bumped on every retie
"""

import base64
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import current_user, fail
from ..live import hub
from ..models import Round, User
from ..people import get_pair

router = APIRouter(prefix="/knot", tags=["knot"])


def _b64(data: bytes | None) -> str | None:
    return base64.b64encode(data).decode() if data is not None else None


def _unb64(value: str, *, exact: int | None = None, max_len: int = 128) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError as e:
        raise ValueError("not base64") from e
    if exact is not None and len(raw) != exact:
        raise ValueError(f"must be {exact} bytes")
    if not 0 < len(raw) <= max_len:
        raise ValueError("wrong length")
    return raw


class KdfParams(BaseModel):
    """Argon2id settings. Bounded so a bad client can't set something that would freeze a phone."""

    alg: Literal["argon2id"] = "argon2id"
    m: int = Field(ge=19_456, le=262_144)  # memory in KiB (19 MiB – 256 MiB)
    t: int = Field(ge=1, le=10)  # passes
    p: int = Field(ge=1, le=4)  # parallelism
    v: Literal[1] = 1  # our own format version, in case the scheme ever changes


class KnotIn(BaseModel):
    kdf_salt: str
    kdf_params: KdfParams
    key_check: str
    key_check_nonce: str
    # For a retie: the version the phone last saw, so two reties can't silently overwrite each other.
    expected_version: int | None = None

    @field_validator("kdf_salt")
    @classmethod
    def _salt(cls, v: str) -> str:
        _unb64(v, exact=16)
        return v

    @field_validator("key_check_nonce")
    @classmethod
    def _nonce(cls, v: str) -> str:
        _unb64(v, exact=12)
        return v

    @field_validator("key_check")
    @classmethod
    def _check(cls, v: str) -> str:
        _unb64(v, max_len=96)
        return v


class KnotOut(BaseModel):
    tied: bool
    key_version: int
    kdf_salt: str | None = None
    kdf_params: dict | None = None
    key_check: str | None = None
    key_check_nonce: str | None = None


def _out(pair) -> KnotOut:
    if pair is None or pair.kdf_salt is None:
        return KnotOut(tied=False, key_version=pair.key_version if pair else 0)
    return KnotOut(
        tied=True,
        key_version=pair.key_version,
        kdf_salt=_b64(pair.kdf_salt),
        kdf_params=pair.kdf_params,
        key_check=_b64(pair.key_check),
        key_check_nonce=_b64(pair.key_check_nonce),
    )


async def _my_pair(db: AsyncSession, user: User, *, lock: bool = False):
    pair = await get_pair(db, lock=lock)
    if pair is None or user.id not in (pair.owner_id, pair.partner_id):
        raise fail(403, "not_paired", "You're not part of this knot.")
    return pair


def _apply(pair, body: KnotIn) -> None:
    pair.kdf_salt = _unb64(body.kdf_salt, exact=16)
    pair.kdf_params = body.kdf_params.model_dump()
    pair.key_check = _unb64(body.key_check, max_len=96)
    pair.key_check_nonce = _unb64(body.key_check_nonce, exact=12)
    pair.key_version += 1


@router.get("", response_model=KnotOut)
async def get_knot(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return _out(await _my_pair(db, user))


@router.post("", response_model=KnotOut)
async def tie(body: KnotIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """First tie. If the other person got there first, answer 409 with the existing knot,
    so this phone switches to 'enter the phrase' instead."""
    pair = await _my_pair(db, user, lock=True)
    if pair.kdf_salt is not None:
        raise fail(409, "already_tied", "This knot is already tied.", knot=_out(pair).model_dump())
    _apply(pair, body)
    await db.commit()
    # The other phone, if it's sitting on "Tie the knot.", switches to "enter the phrase".
    await hub.to_pair({"type": "knot", "key_version": pair.key_version, "by": str(user.id)})
    return _out(pair)


@router.put("", response_model=KnotOut)
async def retie(body: KnotIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Change the phrase. Anything sealed under the old key can never be opened again,
    so open rounds and their sealed answers are deleted."""
    pair = await _my_pair(db, user, lock=True)
    if pair.kdf_salt is None:
        raise fail(409, "not_tied", "Tie the knot first.")
    if body.expected_version is not None and body.expected_version != pair.key_version:
        raise fail(409, "version_changed", "The phrase was just changed on the other phone.", knot=_out(pair).model_dump())
    _apply(pair, body)
    await db.execute(delete(Round))  # sealed_answers go with them (ON DELETE CASCADE)
    await db.commit()
    # The other phone's key is now stale: it'll ask for the new phrase.
    await hub.to_pair({"type": "knot", "key_version": pair.key_version, "by": str(user.id)})
    return _out(pair)
