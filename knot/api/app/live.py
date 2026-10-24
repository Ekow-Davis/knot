"""Live updates over one WebSocket per open app.

Writes always go through normal REST endpoints (easy to validate and test). After a write
commits, the endpoint calls `hub.to_pair(...)` and both phones get the change within a moment.
The socket itself only carries: hello, presence, pings, and those broadcasts.

Kept in memory, which is right for one Railway instance. If the server restarts, phones
reconnect on their own and re-fetch state.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .config import get_settings
from .db import SessionLocal
from .deps import cookie_name, session_user
from .people import get_pair

log = logging.getLogger("knot.live")


class Hub:
    def __init__(self) -> None:
        self.conns: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        # Who has tapped "I'm ready" for the next card. Live-only: leaving the app clears it.
        self.ready: set[uuid.UUID] = set()
        # Which screen each person is on ("play", "home", "settings"…), so the other phone can say
        # "Ama went back to the home screen" instead of silently waiting.
        self.where: dict[uuid.UUID, str] = {}
        # Connected, but the app isn't on screen (tab in the background, phone locked, switched
        # apps). iOS can leave a suspended socket looking alive for minutes, so the phone says so
        # itself. Only notifications use this; the game still treats them as here.
        self.hidden: set[uuid.UUID] = set()

    def online(self, user_id: uuid.UUID | None) -> bool:
        return bool(user_id and self.conns.get(user_id))

    def reachable(self, user_id: uuid.UUID | None) -> bool:
        """Would they see a live toast right now? If not, send a notification instead."""
        return self.online(user_id) and user_id not in self.hidden

    def add(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self.conns[user_id].add(ws)

    def remove(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self.conns[user_id].discard(ws)
        if not self.conns[user_id]:
            del self.conns[user_id]

    async def send(self, user_id: uuid.UUID | None, message: dict) -> None:
        if not user_id:
            return
        for ws in list(self.conns.get(user_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # a dead socket; its own handler will clean it up
                pass

    async def to_users(self, user_ids, message: dict) -> None:
        await asyncio.gather(*(self.send(u, message) for u in {u for u in user_ids if u}))

    async def to_pair(self, message: dict) -> None:
        """Send to both people (every open app of each)."""
        async with SessionLocal() as db:
            pair = await get_pair(db)
        if pair:
            await self.to_users((pair.owner_id, pair.partner_id), message)

    def reset(self) -> None:
        self.conns.clear()
        self.ready.clear()
        self.where.clear()
        self.hidden.clear()


hub = Hub()
router = APIRouter()

SCREENS = {"play", "home", "settings", "unlock", "tonight"}


async def _current_partner(user_id: uuid.UUID) -> uuid.UUID | None:
    async with SessionLocal() as db:
        return _partner_of(await get_pair(db), user_id)


def _partner_of(pair, user_id: uuid.UUID) -> uuid.UUID | None:
    if pair is None:
        return None
    return pair.partner_id if pair.owner_id == user_id else pair.owner_id


@router.websocket("/ws")
async def live(ws: WebSocket) -> None:
    s = get_settings()
    # Browsers always send Origin on WebSockets; in production it must be the app itself.
    if s.is_production and ws.headers.get("origin") != s.app_origin:
        await ws.close(code=4403)
        return

    async with SessionLocal() as db:
        user, _, problem = await session_user(db, ws.cookies.get(cookie_name()))
        pair = await get_pair(db) if user else None
    if user is None:
        # 4401 = "sign in again" for the web app (WebSocket close codes 4000–4999 are ours).
        await ws.close(code=4401, reason=problem)
        return

    partner_id = _partner_of(pair, user.id)
    await ws.accept()
    first_connection = not hub.online(user.id)
    hub.add(user.id, ws)
    hub.hidden.discard(user.id)  # a fresh connection means the app is open
    try:
        await ws.send_json(
            {
                "type": "hello",
                "partner_online": hub.online(partner_id),
                "partner_ready": bool(partner_id and partner_id in hub.ready),
                "partner_where": hub.where.get(partner_id, "") if partner_id else "",
            }
        )
        if first_connection:
            await hub.send(partner_id, {"type": "presence", "online": True})
        while True:
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
            elif msg.get("type") == "away":
                hub.hidden.add(user.id)
            elif msg.get("type") == "back":
                hub.hidden.discard(user.id)
            elif msg.get("type") == "where" and msg.get("screen") in SCREENS:
                # Purely informational, so it rides the socket rather than the REST API.
                hub.where[user.id] = msg["screen"]
                await hub.send(partner_id or await _current_partner(user.id), {"type": "where", "screen": msg["screen"]})
            # Anything else from the phone is ignored: real changes go through the REST API.
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        log.exception("live socket error")
    finally:
        hub.remove(user.id, ws)
        if not hub.online(user.id):
            hub.ready.discard(user.id)  # closed the app: no longer "ready"
            hub.where.pop(user.id, None)
            hub.hidden.discard(user.id)
            # Look the partner up again: they may have joined after this socket opened.
            with contextlib.suppress(Exception):
                async with SessionLocal() as db:
                    partner_now = _partner_of(await get_pair(db), user.id)
                await hub.send(partner_now, {"type": "presence", "online": False})
