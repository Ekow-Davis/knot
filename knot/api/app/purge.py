"""Housekeeping: delete what's no longer needed. Runs every 10 minutes while the server is up."""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, or_

from .db import SessionLocal
from .deps import now
from .models import EmailCode, Invite, Round, Session

log = logging.getLogger("knot.purge")

INTERVAL_SECONDS = 600


async def purge_once() -> int:
    """Returns how many expired rounds were removed."""
    t = now()
    async with SessionLocal() as db:
        # Used or expired codes have no further purpose. A day's grace keeps the
        # 60-second resend check working right after a code is used.
        await db.execute(
            delete(EmailCode).where(
                or_(EmailCode.expires_at < t - timedelta(days=1), EmailCode.consumed_at < t - timedelta(days=1))
            )
        )
        await db.execute(delete(Session).where(Session.expires_at < t))
        await db.execute(
            delete(Invite).where(
                or_(Invite.expires_at < t, Invite.revoked_at.is_not(None), Invite.used_at.is_not(None))
            )
        )
        # Rounds sealed for 24 hours without a reveal: let go, unopened (answers cascade).
        expired = (await db.execute(delete(Round).where(Round.expires_at < t).returning(Round.id))).scalars().all()
        await db.commit()

    if expired:
        from .live import hub  # avoid an import cycle at module load

        for rid in expired:
            await hub.to_pair({"type": "round.expired", "round_id": str(rid)})
    return len(expired)


async def purge_forever() -> None:
    while True:
        try:
            await purge_once()
        except Exception:  # never let housekeeping take the server down
            log.exception("purge failed")
        await asyncio.sleep(INTERVAL_SECONDS)
