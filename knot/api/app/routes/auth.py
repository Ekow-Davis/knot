"""Sign-in: email → 6-digit code → (first time) pairing code → name.

Privacy rule for every endpoint here: the response must never reveal whether an email is
allowed in. Requesting a code always answers the same way, and the email is only actually
sent when that address could really get in.
"""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..deps import (
    clear_session_cookie,
    client_ip,
    code_requests_per_ip,
    cookie_name,
    current_user,
    fail,
    limit,
    now,
    pair_attempts_per_ip,
    pair_attempts_per_ticket,
    start_session,
    verify_attempts_per_ip,
)
from ..live import hub
from ..mail import send_code
from ..models import EmailCode, Invite, Pair, Session, User
from ..people import build_me, get_pair, user_by_email
from ..schemas import CodeRequest, CodeRequested, InviteCheck, JoinRequest, MeOut, VerifyRequest, VerifyResult
from ..security import (
    hash_token,
    keyed_hash,
    make_ticket,
    new_email_code,
    normalize_email,
    normalize_invite,
    read_ticket,
    same,
)

router = APIRouter(prefix="/auth", tags=["auth"])

TICKET_TTL = 15 * 60


def _active_invite_filter():
    return (Invite.used_at.is_(None), Invite.revoked_at.is_(None), Invite.expires_at > now())


async def _can_get_in(db: AsyncSession, email: str) -> bool:
    """Would a code for this email lead anywhere? If not, we quietly don't send one."""
    if await user_by_email(db, email):
        return True
    pair = await get_pair(db)
    s = get_settings()
    if pair is None:
        return bool(s.owner_email) and email == s.owner_email
    if pair.partner_id is None:
        # Second seat is open only while an unused pairing code exists.
        return bool((await db.execute(select(exists().where(*_active_invite_filter())))).scalar())
    return False


# ── 1. Request a code ─────────────────────────────────────────────────────────


@router.post("/code", response_model=CodeRequested)
async def request_code(
    body: CodeRequest, request: Request, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    s = get_settings()
    limit(code_requests_per_ip, client_ip(request))
    email = normalize_email(body.email)

    if await _can_get_in(db, email):
        latest = (
            await db.execute(
                select(EmailCode).where(EmailCode.email == email).order_by(EmailCode.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        cooling_down = latest and now() - latest.created_at < timedelta(seconds=s.code_resend_seconds)

        if not cooling_down:
            # A new code replaces any older one ("try the newest email").
            await db.execute(
                update(EmailCode)
                .where(EmailCode.email == email, EmailCode.consumed_at.is_(None))
                .values(consumed_at=now())
            )
            code = new_email_code()
            db.add(
                EmailCode(
                    email=email,
                    code_hmac=keyed_hash(s.secret_key, "email", f"{email}:{code}"),
                    expires_at=now() + timedelta(minutes=s.code_ttl_minutes),
                )
            )
            await db.commit()
            # Sent after the response, so response time doesn't hint at whether an email went out.
            background.add_task(send_code, email, code)

    return CodeRequested(resend_after=s.code_resend_seconds)


# ── 2. Verify it ──────────────────────────────────────────────────────────────


@router.post("/verify", response_model=VerifyResult)
async def verify_code(body: VerifyRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    limit(verify_attempts_per_ip, client_ip(request))
    email = normalize_email(body.email)

    row = (
        await db.execute(
            select(EmailCode)
            .where(EmailCode.email == email, EmailCode.consumed_at.is_(None))
            .order_by(EmailCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if row is None:
        # Same message as a wrong code, so nobody learns whether a code was ever sent.
        raise fail(400, "code_wrong", "That code doesn't match. Try the newest email.")
    if row.expires_at < now():
        raise fail(400, "code_expired", "That code has expired. Grab a fresh one below.")

    if not same(row.code_hmac, keyed_hash(s.secret_key, "email", f"{email}:{body.code}")):
        row.attempts += 1
        if row.attempts >= s.code_max_attempts:
            row.consumed_at = now()  # burned: they need a new one
            await db.commit()
            raise fail(400, "code_expired", "Too many tries on that code. Grab a fresh one below.")
        await db.commit()
        raise fail(
            400,
            "code_wrong",
            "That code doesn't match. Try the newest email.",
            attempts_left=s.code_max_attempts - row.attempts,
        )

    row.consumed_at = now()
    await db.commit()

    user = await user_by_email(db, email)
    if user:
        await start_session(db, response, user, request.headers.get("user-agent"))
        return VerifyResult(status="signed_in", me=await build_me(db, user))

    pair = await get_pair(db)
    ticket = make_ticket(s.secret_key, email, TICKET_TTL)
    if pair is None and s.owner_email and email == s.owner_email:
        return VerifyResult(status="new_owner", ticket=ticket)
    return VerifyResult(status="needs_pairing", ticket=ticket)


# ── 3. (First time) check a pairing code ──────────────────────────────────────


def _read_ticket_or_fail(ticket: str) -> dict:
    t = read_ticket(get_settings().secret_key, ticket)
    if t is None:
        raise fail(400, "ticket_expired", "That took a while. Start again with your email.")
    return t


async def _find_invite(db: AsyncSession, raw_code: str, *, lock: bool = False) -> Invite | None:
    code_hmac = keyed_hash(get_settings().secret_key, "invite", normalize_invite(raw_code))
    q = select(Invite).where(Invite.code_hmac == code_hmac, *_active_invite_filter())
    if lock:
        q = q.with_for_update()
    return (await db.execute(q)).scalar_one_or_none()


@router.post("/check-invite")
async def check_invite(body: InviteCheck, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Lets the pairing screen say 'that code didn't work' before asking for a name."""
    t = _read_ticket_or_fail(body.ticket)
    limit(pair_attempts_per_ip, client_ip(request))
    limit(pair_attempts_per_ticket, t["n"])

    pair = await get_pair(db)
    if pair is not None and pair.partner_id is not None:
        raise fail(409, "pair_full", "This pair is already complete.")
    if pair is None or await _find_invite(db, body.invite_code) is None:
        raise fail(400, "invite_invalid", "That code didn't work. Check it with whoever sent it.")
    return {"ok": True}


# ── 4. Create the account (owner, or partner with a pairing code) ─────────────


@router.post("/join", response_model=MeOut)
async def join(body: JoinRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    t = _read_ticket_or_fail(body.ticket)
    email = t["e"]
    ua = request.headers.get("user-agent")

    # Already has an account (e.g. double-tapped the button): just sign in.
    existing = await user_by_email(db, email)
    if existing:
        await start_session(db, response, existing, ua)
        return await build_me(db, existing)

    pair = await get_pair(db, lock=True)

    if pair is None:
        # Only the owner can create the pair, and only once.
        if not s.owner_email or email != s.owner_email:
            raise fail(400, "invite_invalid", "That code didn't work. Check it with whoever sent it.")
        user = User(email=email, display_name=body.display_name)
        db.add(user)
        await db.flush()
        db.add(Pair(id=1, owner_id=user.id, turn_user_id=user.id))
    else:
        if pair.partner_id is not None:
            raise fail(409, "pair_full", "This pair is already complete.")
        limit(pair_attempts_per_ip, client_ip(request))
        limit(pair_attempts_per_ticket, t["n"])
        invite = await _find_invite(db, body.invite_code or "", lock=True)
        if invite is None:
            raise fail(400, "invite_invalid", "That code didn't work. Check it with whoever sent it.")
        user = User(email=email, display_name=body.display_name)
        db.add(user)
        await db.flush()
        pair.partner_id = user.id
        invite.used_at = now()
        invite.used_by = user.id

    try:
        await db.commit()
    except IntegrityError:
        # Two joins raced (same email twice, or two owners at once). The database kept one.
        await db.rollback()
        raise fail(409, "pair_full", "This pair is already complete.")

    if pair is not None:
        # She just joined: the owner's open app updates from "waiting for two" to paired.
        await hub.send(pair.owner_id, {"type": "pair", "complete": True})
    await start_session(db, response, user, ua)
    return await build_me(db, user)


# ── Session ───────────────────────────────────────────────────────────────────


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await build_me(db, user)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> None:
    token = request.cookies.get(cookie_name())
    if token:
        sess = (await db.execute(select(Session).where(Session.token_hash == hash_token(token)))).scalar_one_or_none()
        if sess:
            await db.delete(sess)
            await db.commit()
    clear_session_cookie(response)
