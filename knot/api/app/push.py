"""Web Push: the notifications that reach a phone when the app isn't open.

Rules (from the design: "Only for two things. Never streaks, never 'we miss you'."):
  • Only ever about the other person: a tug, a sealed question left for you, an answer waiting.
  • Never the question text or anyone's answer.
  • Only sent when the person's app isn't open (if it is, the live connection already shows it).

On iPhone this works only once the app is on the Home Screen, served over HTTPS, and the
person has tapped "Allow tugs".
"""

import asyncio
import json
import logging
import uuid

from sqlalchemy import delete, select

from .config import get_settings
from .db import SessionLocal
from .models import PushSubscription

log = logging.getLogger("knot.push")
# Shown in the API's console next to the request log, so you can see whether a notification
# went out and what Apple/Google said about it.
say = logging.getLogger("uvicorn.error")


def configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def _send_one(sub: PushSubscription, payload: dict) -> int:
    """Blocking (pywebpush uses requests), so it runs in a thread. Returns the HTTP status."""
    from pywebpush import WebPushException, webpush

    s = get_settings()
    try:
        r = webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=json.dumps(payload),
            vapid_private_key=s.vapid_private_key,
            vapid_claims={"sub": s.vapid_subject},
            ttl=60 * 60 * 24,
            timeout=10,
        )
        return r.status_code
    except WebPushException as e:
        code = e.response.status_code if e.response is not None else 0
        detail = (e.response.text[:200] if e.response is not None else str(e)).strip()
        say.warning("push: %s refused it (%s): %s", sub.endpoint.split("/")[2], code, detail)
        return code
    except Exception:  # network trouble: try again next time
        log.exception("push send failed")
        return 0


async def notify(user_id: uuid.UUID | None, title: str, body: str, *, tag: str, url: str = "/") -> int:
    """Send to every phone this person has allowed notifications on. Returns how many accepted."""
    if not user_id or not configured():
        if user_id:
            say.info("push: not sent (VAPID keys aren't set)")
        return 0
    async with SessionLocal() as db:
        subs = (await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
    if not subs:
        say.info("push: not sent (they haven't allowed notifications on any device yet)")
        return 0

    payload = {"title": title, "body": body, "tag": tag, "url": url}
    statuses = await asyncio.gather(*(asyncio.to_thread(_send_one, s, payload) for s in subs))

    # 404/410: the phone dropped this subscription (app removed, permission revoked). Forget it.
    gone = [s.endpoint for s, code in zip(subs, statuses) if code in (404, 410)]
    if gone:
        async with SessionLocal() as db:
            await db.execute(delete(PushSubscription).where(PushSubscription.endpoint.in_(gone)))
            await db.commit()
    ok = sum(1 for c in statuses if 200 <= c < 300)
    say.info("push: \"%s %s\" delivered to %d of %d device(s)", title, body, ok, len(subs))
    return ok


def notify_later(user_id, title: str, body: str, *, tag: str, url: str = "/") -> None:
    """Fire and forget: never make a request wait on Apple's or Google's push servers."""
    if not user_id or not configured():
        return
    task = asyncio.create_task(notify(user_id, title, body, tag=tag, url=url))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


_pending: set[asyncio.Task] = set()
