"""Pairing codes. Only the owner can make one, and only while the second seat is empty."""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..deps import current_user, fail, now
from ..models import Invite, User
from ..people import get_pair
from ..schemas import InviteOut, InviteStatus
from ..security import keyed_hash, new_invite_code

router = APIRouter(prefix="/invites", tags=["invites"])


async def _owner_pair(db: AsyncSession, user: User):
    pair = await get_pair(db, lock=True)
    if pair is None or pair.owner_id != user.id:
        raise fail(403, "not_owner", "Only the person who set this up can invite.")
    return pair


@router.post("", response_model=InviteOut)
async def create_invite(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Make a fresh TIE-XXXXX code. Any older unused code stops working.
    The plain code is returned exactly once — only its HMAC is stored."""
    s = get_settings()
    pair = await _owner_pair(db, user)
    if pair.partner_id is not None:
        raise fail(409, "pair_full", "You're already paired.")

    await db.execute(
        update(Invite).where(Invite.used_at.is_(None), Invite.revoked_at.is_(None)).values(revoked_at=now())
    )
    code = new_invite_code()
    expires_at = now() + timedelta(days=s.invite_ttl_days)
    db.add(Invite(code_hmac=keyed_hash(s.secret_key, "invite", code), created_by=user.id, expires_at=expires_at))
    await db.commit()
    return InviteOut(code=code, expires_at=expires_at)


@router.get("/status", response_model=InviteStatus)
async def invite_status(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair = await get_pair(db)
    pending = (
        await db.execute(
            select(Invite.expires_at)
            .where(Invite.used_at.is_(None), Invite.revoked_at.is_(None), Invite.expires_at > now())
            .order_by(Invite.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return InviteStatus(pair_complete=bool(pair and pair.partner_id), pending_invite_expires_at=pending)


@router.delete("", status_code=204)
async def revoke_invites(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> None:
    """Cancel any outstanding code (e.g. you sent it to the wrong chat)."""
    await _owner_pair(db, user)
    await db.execute(
        update(Invite).where(Invite.used_at.is_(None), Invite.revoked_at.is_(None)).values(revoked_at=now())
    )
    await db.commit()
