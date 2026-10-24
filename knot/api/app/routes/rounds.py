"""Playing: draw → answer and seal → pull (reveal) → gone.

Who answers:
  guess  → both. The drawer guesses; the other person (the "subject") writes the truth.
  both   → both.
  wyr    → both (each picks A or B).
  self   → only the drawer ("Just you"); the other person reads it.

Revealing ("pulling your end"):
  • Both pulled → both phones get the answers at once, then the round and its answers are deleted.
  • The other person is away → you can read it now; it waits for their pull (or expires in 24h).
  • The other person is here but hasn't pulled → you wait, or choose to read it alone.

The server only ever handles answers as ciphertext. Question text is decrypted for the
two phones at the moment a round is opened.
"""

import base64
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..bank import BankKeyMissing, bank_key, open_question
from ..config import get_settings
from ..db import get_db
from ..deps import Limiter, current_user, fail, limit, now
from ..live import hub
from ..mix import categories_in_play
from ..models import DrawnQuestion, Pair, Question, Round, SealedAnswer, User
from ..people import get_pair

router = APIRouter(prefix="/rounds", tags=["rounds"])
tugs_per_user = Limiter(1, 10)  # one tug every 10 seconds is plenty

MAX_ANSWER_BYTES = 8000  # ciphertext; roughly 2,000 words


# ── Shapes ────────────────────────────────────────────────────────────────────


class QuestionOut(BaseModel):
    id: str
    type: Literal["guess", "both", "wyr", "self"]
    depth: str
    category: str
    text: str  # may contain {p}: the app swaps in the subject's name
    options: list[str] | None = None


class RoundOut(BaseModel):
    id: uuid.UUID
    question: QuestionOut
    drawn_by: uuid.UUID
    subject_id: uuid.UUID | None
    state: Literal["open", "ready"]
    i_answer: bool  # does this phone's person write an answer?
    i_sealed: bool
    partner_answers: bool
    partner_sealed: bool
    pulled_by: list[uuid.UUID]
    expires_at: str
    key_version: int


class CurrentOut(BaseModel):
    round: RoundOut | None


class SealIn(BaseModel):
    ciphertext: str
    nonce: str
    key_version: int

    @field_validator("ciphertext")
    @classmethod
    def _ct(cls, v: str) -> str:
        raw = base64.b64decode(v, validate=True)
        if not 16 < len(raw) <= MAX_ANSWER_BYTES:
            raise ValueError("answer too long")
        return v

    @field_validator("nonce")
    @classmethod
    def _n(cls, v: str) -> str:
        if len(base64.b64decode(v, validate=True)) != 12:
            raise ValueError("nonce must be 12 bytes")
        return v


class HoldIn(BaseModel):
    holding: bool


class PullIn(BaseModel):
    alone: bool = False  # read it now without waiting for the other person


class VerdictIn(BaseModel):
    match: bool


class AnswerOut(BaseModel):
    user_id: uuid.UUID
    ciphertext: str
    nonce: str
    key_version: int


class PullOut(BaseModel):
    revealed: bool
    answers: list[AnswerOut] = Field(default_factory=list)
    question: QuestionOut | None = None
    turn_user_id: uuid.UUID | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _pair(db: AsyncSession, user: User, *, lock: bool = False) -> tuple[Pair, uuid.UUID | None]:
    pair = await get_pair(db, lock=lock)
    if pair is None or user.id not in (pair.owner_id, pair.partner_id):
        raise fail(403, "not_paired", "You're not part of this knot.")
    partner_id = pair.partner_id if pair.owner_id == user.id else pair.owner_id
    return pair, partner_id


def _answerers(rnd: Round, q: Question, pair: Pair) -> set[uuid.UUID]:
    if q.type == "self":
        return {rnd.drawn_by}
    return {u for u in (pair.owner_id, pair.partner_id) if u}


def _other(pair: Pair, user_id: uuid.UUID) -> uuid.UUID | None:
    return pair.partner_id if pair.owner_id == user_id else pair.owner_id


def _question_out(q: Question) -> QuestionOut:
    try:
        payload = open_question(bank_key(), q.id, q.payload, q.payload_nonce)
    except BankKeyMissing as e:
        raise fail(503, "bank_key_missing", "The question bank isn't set up on the server yet.") from e
    return QuestionOut(
        id=q.id, type=q.type, depth=q.depth, category=q.category, text=payload["q"], options=payload.get("options")
    )


async def _round_out(db: AsyncSession, rnd: Round, user: User, pair: Pair) -> RoundOut:
    q = await db.get(Question, rnd.question_id)
    sealed = set((await db.execute(select(SealedAnswer.user_id).where(SealedAnswer.round_id == rnd.id))).scalars())
    who = _answerers(rnd, q, pair)
    partner = _other(pair, user.id)
    return RoundOut(
        id=rnd.id,
        question=_question_out(q),
        drawn_by=rnd.drawn_by,
        subject_id=rnd.subject_id,
        state=rnd.state,
        i_answer=user.id in who,
        i_sealed=user.id in sealed,
        partner_answers=partner in who,
        partner_sealed=partner in sealed,
        pulled_by=list(rnd.pulled_by or []),
        expires_at=rnd.expires_at.isoformat(),
        key_version=pair.key_version,
    )


async def _live_round(db: AsyncSession, round_id: uuid.UUID, *, lock: bool = False) -> Round:
    q = select(Round).where(Round.id == round_id)
    if lock:
        q = q.with_for_update()
    rnd = (await db.execute(q)).scalar_one_or_none()
    if rnd is None or rnd.expires_at < now():
        raise fail(404, "round_gone", "That one's already been let go.")
    return rnd


async def _finish(db: AsyncSession, pair: Pair, rnd: Round) -> None:
    """Round over (revealed by both, passed, or retired): delete it, hand the turn over."""
    pair.turn_user_id = _other(pair, rnd.drawn_by) or rnd.drawn_by
    await db.execute(delete(Round).where(Round.id == rnd.id))  # sealed answers cascade


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/current", response_model=CurrentOut)
async def current(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair, _ = await _pair(db, user)
    rnd = (await db.execute(select(Round).where(Round.expires_at > now()))).scalar_one_or_none()
    return CurrentOut(round=await _round_out(db, rnd, user, pair) if rnd else None)


async def _draw_for(db: AsyncSession, pair: Pair, drawer_id: uuid.UUID) -> Round:
    """Deal a card from the shared hat. `drawer_id` decides who guesses (Guess cards) and who
    writes (Just you cards). Raises 409 round_open / empty."""
    partner_id = _other(pair, drawer_id)
    # An expired round the cleanup job hasn't reached yet must not block a new one.
    await db.execute(delete(Round).where(Round.expires_at <= now()))
    if (await db.execute(select(Round.id).where(Round.expires_at > now()))).first():
        raise fail(409, "round_open", "There's already one on the table.")

    drawer = await db.get(User, drawer_id)
    partner = await db.get(User, partner_id) if partner_id else None
    cats = categories_in_play(pair.settings, bool(drawer and drawer.spicy_on and partner and partner.spicy_on))
    q = (
        await db.execute(
            select(Question)
            .where(
                Question.retired_at.is_(None),
                Question.depth == pair.settings["depth"],
                Question.category.in_(cats),
                ~Question.id.in_(select(DrawnQuestion.question_id)),
            )
            .order_by(text("random()"))
            .limit(1)
        )
    ).scalar_one_or_none()
    if q is None:
        raise fail(409, "empty", "You've drawn every card in this mix.")

    subject = partner_id if q.type == "guess" else drawer_id if q.type == "self" else None
    rnd = Round(
        question_id=q.id,
        drawn_by=drawer_id,
        subject_id=subject,
        state="open",
        pulled_by=[],
        expires_at=now() + timedelta(hours=get_settings().round_ttl_hours),
    )
    db.add(rnd)
    db.add(DrawnQuestion(question_id=q.id))
    try:
        await db.flush()
    except IntegrityError as e:  # another draw won the race
        await db.rollback()
        raise fail(409, "round_open", "There's already one on the table.") from e
    return rnd


@router.post("", response_model=RoundOut)
async def draw(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Draw on your own: only while the other person is away ("leave a sealed question").
    When you're both here, use /ready: the card appears once you're both ready."""
    pair, partner_id = await _pair(db, user, lock=True)
    if partner_id is None:
        raise fail(409, "not_paired_yet", "Pair up first.")
    if hub.online(partner_id):
        raise fail(409, "use_ready", "You're both here: tap ready together.")
    rnd = await _draw_for(db, pair, user.id)
    out = await _round_out(db, rnd, user, pair)
    await db.commit()
    hub.ready.clear()
    await hub.send(partner_id, {"type": "round.drawn", "round_id": str(rnd.id), "by": str(user.id)})
    return out


class ReadyIn(BaseModel):
    ready: bool


class ReadyOut(BaseModel):
    drawn: bool
    empty: bool = False
    round: RoundOut | None = None
    ready_me: bool = False
    ready_them: bool = False


@router.post("/ready", response_model=ReadyOut)
async def ready(body: ReadyIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Both here: each taps "I'm ready". When both are, a card is dealt to both phones at once.
    The drawer alternates behind the scenes (pair.turn_user_id), so Guess and Just-you roles
    swap from round to round."""
    pair, partner_id = await _pair(db, user, lock=True)
    if partner_id is None:
        raise fail(409, "not_paired_yet", "Pair up first.")
    if body.ready:
        hub.ready.add(user.id)
    else:
        hub.ready.discard(user.id)

    both = user.id in hub.ready and partner_id in hub.ready
    if not both:
        await db.commit()
        await hub.send(partner_id, {"type": "ready", "user_id": str(user.id), "ready": body.ready})
        return ReadyOut(drawn=False, ready_me=user.id in hub.ready, ready_them=partner_id in hub.ready)

    hub.ready.discard(user.id)
    hub.ready.discard(partner_id)
    drawer = pair.turn_user_id if pair.turn_user_id in (pair.owner_id, pair.partner_id) else pair.owner_id
    try:
        rnd = await _draw_for(db, pair, drawer)
    except HTTPException as e:
        code = e.detail.get("code") if isinstance(e.detail, dict) else ""
        if code == "empty":
            await hub.to_pair({"type": "round.empty"})
            return ReadyOut(drawn=False, empty=True)
        if code == "round_open":
            await hub.to_pair({"type": "round.drawn", "round_id": "", "by": ""})
            return ReadyOut(drawn=False)
        raise
    out = await _round_out(db, rnd, user, pair)
    await db.commit()
    await hub.to_pair({"type": "round.drawn", "round_id": str(rnd.id), "by": str(drawer)})
    return ReadyOut(drawn=True, round=out)


@router.post("/reshuffle")
async def reshuffle(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """'Shuffle them back in': forget which cards in the current mix were drawn."""
    pair, partner_id = await _pair(db, user)
    partner = await db.get(User, partner_id) if partner_id else None
    cats = categories_in_play(pair.settings, user.spicy_on and bool(partner and partner.spicy_on))
    ids = select(Question.id).where(Question.depth == pair.settings["depth"], Question.category.in_(cats))
    n = (await db.execute(delete(DrawnQuestion).where(DrawnQuestion.question_id.in_(ids)))).rowcount
    await db.commit()
    return {"shuffled_back": n}


@router.post("/{round_id}/seal", response_model=RoundOut)
async def seal(round_id: uuid.UUID, body: SealIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair, partner_id = await _pair(db, user, lock=True)
    rnd = await _live_round(db, round_id, lock=True)
    q = await db.get(Question, rnd.question_id)
    who = _answerers(rnd, q, pair)
    if user.id not in who:
        raise fail(403, "not_yours", "This one's theirs to answer.")
    if body.key_version != pair.key_version:
        raise fail(409, "stale_key", "The phrase changed. Enter the new one to answer.")
    if await db.get(SealedAnswer, (rnd.id, user.id)):
        raise fail(409, "already_sealed", "You've already sealed this one.")

    db.add(
        SealedAnswer(
            round_id=rnd.id,
            user_id=user.id,
            ciphertext=base64.b64decode(body.ciphertext),
            nonce=base64.b64decode(body.nonce),
            key_version=body.key_version,
        )
    )
    await db.flush()
    sealed = set((await db.execute(select(SealedAnswer.user_id).where(SealedAnswer.round_id == rnd.id))).scalars())
    if who <= sealed:
        rnd.state = "ready"
    out = await _round_out(db, rnd, user, pair)
    await db.commit()
    await hub.send(
        partner_id, {"type": "round.sealed", "round_id": str(rnd.id), "by": str(user.id), "ready": rnd.state == "ready"}
    )
    return out


async def _end_without_reveal(db, pair, rnd, user, *, retire: bool) -> dict:
    if retire:
        q = await db.get(Question, rnd.question_id)
        q.retired_at = now()
    await _finish(db, pair, rnd)
    await db.commit()
    await hub.to_pair(
        {
            "type": "round.passed",
            "round_id": str(rnd.id),
            "by": str(user.id),
            "retired": retire,
            "turn_user_id": str(pair.turn_user_id),
        }
    )
    return {"ok": True, "turn_user_id": str(pair.turn_user_id)}


@router.post("/{round_id}/pass")
async def pass_round(round_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """No reason needed. Any sealed answers are deleted unread."""
    pair, _ = await _pair(db, user, lock=True)
    rnd = await _live_round(db, round_id, lock=True)
    return await _end_without_reveal(db, pair, rnd, user, retire=False)


@router.post("/{round_id}/retire")
async def retire(round_id: uuid.UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """'Never show this one again': takes the question out of the bank for good, then passes."""
    pair, _ = await _pair(db, user, lock=True)
    rnd = await _live_round(db, round_id, lock=True)
    return await _end_without_reveal(db, pair, rnd, user, retire=True)


@router.post("/{round_id}/hold")
async def hold(round_id: uuid.UUID, body: HoldIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Purely for the animation: the other phone sees your half of the ring filling."""
    _, partner_id = await _pair(db, user)
    await hub.send(partner_id, {"type": "round.hold", "round_id": str(round_id), "holding": body.holding})
    return {"ok": True}


@router.post("/{round_id}/pull", response_model=PullOut)
async def pull(round_id: uuid.UUID, body: PullIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    pair, partner_id = await _pair(db, user, lock=True)
    rnd = await _live_round(db, round_id, lock=True)
    if rnd.state != "ready":
        raise fail(409, "not_ready", "Still waiting on an answer.")

    pulled = set(rnd.pulled_by or [])
    pulled.add(user.id)
    rnd.pulled_by = list(pulled)

    rows = (await db.execute(select(SealedAnswer).where(SealedAnswer.round_id == rnd.id))).scalars().all()
    answers = [
        AnswerOut(
            user_id=a.user_id,
            ciphertext=base64.b64encode(a.ciphertext).decode(),
            nonce=base64.b64encode(a.nonce).decode(),
            key_version=a.key_version,
        )
        for a in rows
    ]
    question = _question_out(await db.get(Question, rnd.question_id))
    everyone = {u for u in (pair.owner_id, pair.partner_id) if u}

    if everyone <= pulled:
        # Both ends pulled: reveal to both, then nothing is kept.
        await _finish(db, pair, rnd)
        await db.commit()
        reveal = PullOut(revealed=True, answers=answers, question=question, turn_user_id=pair.turn_user_id)
        await hub.send(
            partner_id,
            {"type": "round.revealed", "round_id": str(rnd.id), **reveal.model_dump(mode="json")},
        )
        return reveal

    if body.alone or not hub.online(partner_id):
        # Read it now; the round stays for their pull (or expires after 24 hours).
        await db.commit()
        await hub.send(partner_id, {"type": "round.pull", "round_id": str(rnd.id), "by": str(user.id), "read": True})
        return PullOut(revealed=True, answers=answers, question=question, turn_user_id=pair.turn_user_id)

    await db.commit()
    await hub.send(partner_id, {"type": "round.pull", "round_id": str(rnd.id), "by": str(user.id), "read": False})
    return PullOut(revealed=False)


@router.post("/{round_id}/verdict")
async def verdict(round_id: uuid.UUID, body: VerdictIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """'Close enough?' from the person who was guessed about. Not stored: the round is already gone."""
    await _pair(db, user)
    await hub.to_pair({"type": "round.verdict", "round_id": str(round_id), "by": str(user.id), "match": body.match})
    return {"ok": True}


@router.post("/tug", include_in_schema=True)
async def tug(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """'Give them a little tug.' Live for now; also a push notification from Session 7."""
    _, partner_id = await _pair(db, user)
    limit(tugs_per_user, str(user.id))
    await hub.send(partner_id, {"type": "tug", "by": str(user.id)})
    return {"ok": True}
