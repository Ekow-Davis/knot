"""Shared request helpers: errors, the signed-in user, session cookies and rate limits."""

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .models import Session, User
from .security import hash_token, new_session_token


def now() -> datetime:
    return datetime.now(timezone.utc)


def fail(status: int, code: str, message: str, **extra) -> HTTPException:
    """Errors look like {"detail": {"code": "...", "message": "...", ...}} — the web app keys off `code`."""
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


# ── Session cookie ────────────────────────────────────────────────────────────


def cookie_name() -> str:
    # "__Host-" makes the browser refuse the cookie unless it's Secure, path=/ and has no Domain:
    # it can't be set or read by any other subdomain of forgottenguardian.com.
    return "__Host-knot" if get_settings().is_production else "knot"


async def start_session(db: AsyncSession, response: Response, user: User, user_agent: str | None) -> None:
    s = get_settings()
    token = new_session_token()
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(token),
            user_agent=(user_agent or "")[:300],
            expires_at=now() + timedelta(days=s.session_ttl_days),
        )
    )
    await db.commit()
    response.set_cookie(
        cookie_name(),
        token,
        max_age=s.session_ttl_days * 86400,
        httponly=True,
        secure=s.is_production,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(cookie_name(), path="/", secure=get_settings().is_production, httponly=True)


async def session_user(db: AsyncSession, token: str | None) -> tuple[User | None, Session | None, str]:
    """Look up the session behind a cookie token. Returns (user, session, problem) where
    problem is "" on success, else "not_signed_in" or "session_expired".
    Shared by normal requests and the live WebSocket."""
    if not token:
        return None, None, "not_signed_in"
    sess = (
        await db.execute(select(Session).where(Session.token_hash == hash_token(token), Session.expires_at > now()))
    ).scalar_one_or_none()
    if sess is None:
        return None, None, "session_expired"

    # Sliding expiry: active use keeps you signed in. Only write at most once an hour.
    if now() - sess.last_used_at > timedelta(hours=1):
        sess.last_used_at = now()
        sess.expires_at = now() + timedelta(days=get_settings().session_ttl_days)
        await db.commit()

    user = await db.get(User, sess.user_id)
    if user is None:
        return None, None, "session_expired"
    return user, sess, ""


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    user, sess, problem = await session_user(db, request.cookies.get(cookie_name()))
    if problem == "not_signed_in":
        raise fail(401, "not_signed_in", "Sign in to continue.")
    if problem:
        raise fail(401, "session_expired", "You've been away a while. Sign in again.")
    request.state.session_id = sess.id
    return user


def session_id(request: Request) -> uuid.UUID | None:
    return getattr(request.state, "session_id", None)


# ── Rate limits ───────────────────────────────────────────────────────────────
# In memory, which is fine for a single Railway instance. Restarting the server resets them;
# the per-code attempt limit in the database still holds regardless.


class Limiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Record a hit. Returns False when the key is over its limit."""
        t = time.monotonic()
        q = self.hits[key]
        while q and q[0] <= t - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(t)
        return True

    def reset(self) -> None:
        self.hits.clear()


code_requests_per_ip = Limiter(10, 3600)
verify_attempts_per_ip = Limiter(30, 3600)
pair_attempts_per_ip = Limiter(20, 3600)
pair_attempts_per_ticket = Limiter(5, 3600)


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers on Railway, so this is the real client address.
    return request.client.host if request.client else "unknown"


def limit(limiter: Limiter, key: str) -> None:
    if not limiter.hit(key):
        raise fail(429, "slow_down", "Too many tries. Give it a little while and try again.")
