"""Turning notifications on and off for this phone."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..deps import current_user, fail
from ..models import PushSubscription, User
from ..push import configured

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(pattern=r"^https://", max_length=1000)
    keys: Keys


class EndpointIn(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.get("/key")
async def public_key(_: User = Depends(current_user)) -> dict:
    if not configured():
        raise fail(503, "push_off", "Notifications aren't set up on the server yet.")
    return {"key": get_settings().vapid_public_key}


@router.post("/subscribe", status_code=204)
async def subscribe(body: SubscriptionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> None:
    existing = (
        await db.execute(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    ).scalar_one_or_none()
    if existing:
        # Same phone, maybe a different person signed in on it now.
        existing.user_id, existing.p256dh, existing.auth = user.id, body.keys.p256dh, body.keys.auth
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth))
    await db.commit()


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(body: EndpointIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> None:
    await db.execute(
        delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id)
    )
    await db.commit()
