"""Loading the pair and building the 'me' view. Used by several routes."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Pair, User
from .schemas import MeOut, PersonOut


async def get_pair(db: AsyncSession, *, lock: bool = False) -> Pair | None:
    q = select(Pair).where(Pair.id == 1)
    if lock:
        q = q.with_for_update()
    return (await db.execute(q)).scalar_one_or_none()


async def user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def build_me(db: AsyncSession, user: User) -> MeOut:
    pair = await get_pair(db)
    role = "owner" if pair and pair.owner_id == user.id else "partner"
    partner_id = None
    if pair:
        partner_id = pair.partner_id if role == "owner" else pair.owner_id
    partner = await db.get(User, partner_id) if partner_id else None
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        theme=user.theme or {},
        spicy_on=user.spicy_on,
        role=role,
        pair_complete=bool(pair and pair.partner_id),
        partner=PersonOut(id=partner.id, display_name=partner.display_name, theme=partner.theme or {})
        if partner
        else None,
    )
