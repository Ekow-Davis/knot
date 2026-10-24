"""The home screen's shared state: depth, the hat (categories / Random / excluded),
each person's Spicy switch, whose turn it is, and whether the other person is here."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import current_user, fail, now
from ..live import hub
from ..mix import HAT, categories_in_play
from ..models import User
from ..people import get_pair

router = APIRouter(tags=["home"])

Category = Literal["cozy", "silly", "sweet", "big", "memories", "future"]  # = mix.HAT (no "spicy")


class SharedSettings(BaseModel):
    depth: Literal["light", "medium", "deep"]
    categories: list[Category]
    random: bool
    excluded: list[Category]

    @model_validator(mode="after")
    def _something_in_the_hat(self):
        # Spicy can't keep the hat non-empty on its own: it depends on both switches.
        self.categories = sorted(set(self.categories), key=HAT.index)
        self.excluded = sorted(set(self.excluded), key=HAT.index)
        if not self.random and not self.categories:
            raise ValueError("Keep at least one in the hat.")
        if self.random and len(self.excluded) >= len(HAT):
            raise ValueError("Keep at least one in the hat.")
        return self


class SettingsPatch(BaseModel):
    depth: Literal["light", "medium", "deep"] | None = None
    categories: list[Category] | None = None
    random: bool | None = None
    excluded: list[Category] | None = None


class SpicyIn(BaseModel):
    on: bool


class HomeOut(BaseModel):
    settings: SharedSettings
    settings_updated_by: uuid.UUID | None
    spicy_me: bool
    spicy_them: bool
    in_play: list[str]
    turn_user_id: uuid.UUID | None
    partner_online: bool
    ready_me: bool = False
    ready_them: bool = False


async def _pair_and_partner(db: AsyncSession, user: User, *, lock: bool = False):
    pair = await get_pair(db, lock=lock)
    if pair is None or user.id not in (pair.owner_id, pair.partner_id):
        raise fail(403, "not_paired", "You're not part of this knot.")
    partner_id = pair.partner_id if pair.owner_id == user.id else pair.owner_id
    partner = await db.get(User, partner_id) if partner_id else None
    return pair, partner


@router.get("/home", response_model=HomeOut)
async def get_home(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair, partner = await _pair_and_partner(db, user)
    spicy_them = bool(partner and partner.spicy_on)
    return HomeOut(
        settings=SharedSettings(**pair.settings),
        settings_updated_by=pair.settings_updated_by,
        spicy_me=user.spicy_on,
        spicy_them=spicy_them,
        in_play=categories_in_play(pair.settings, user.spicy_on and spicy_them),
        turn_user_id=pair.turn_user_id,
        partner_online=hub.online(partner.id if partner else None),
        ready_me=user.id in hub.ready,
        ready_them=bool(partner and partner.id in hub.ready),
    )


@router.patch("/settings", response_model=SharedSettings)
async def update_settings(body: SettingsPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair, _ = await _pair_and_partner(db, user, lock=True)
    merged = {**pair.settings, **body.model_dump(exclude_none=True)}
    # Turning Random on or off starts its exclusions fresh (as in the design).
    if body.random is not None and body.random != pair.settings.get("random") and body.excluded is None:
        merged["excluded"] = []
    try:
        settings = SharedSettings(**merged)
    except ValueError as e:
        raise fail(422, "empty_hat", "Keep at least one in the hat.") from e

    pair.settings = settings.model_dump()
    pair.settings_updated_by = user.id
    pair.settings_updated_at = now()
    await db.commit()
    await hub.to_pair({"type": "settings", "settings": pair.settings, "by": str(user.id)})
    return settings


@router.put("/me/spicy")
async def set_spicy(body: SpicyIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Your own Spicy switch. Spicy questions only come up when both are on."""
    await _pair_and_partner(db, user)
    user.spicy_on = body.on
    await db.commit()
    await hub.to_pair({"type": "spicy", "user_id": str(user.id), "on": body.on})
    return {"on": body.on}
