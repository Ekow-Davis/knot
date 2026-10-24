"""Your own profile: display name and theme."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import current_user
from ..live import hub
from ..models import User
from ..people import build_me
from ..schemas import MeOut, MeUpdate

router = APIRouter(prefix="/me", tags=["me"])


@router.patch("", response_model=MeOut)
async def update_me(body: MeUpdate, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.theme is not None:
        user.theme = body.theme.model_dump()
    await db.commit()
    # The other phone uses your name everywhere, and your accent colour for your cards.
    await hub.to_pair(
        {"type": "profile", "user_id": str(user.id), "display_name": user.display_name, "theme": user.theme}
    )
    return await build_me(db, user)
