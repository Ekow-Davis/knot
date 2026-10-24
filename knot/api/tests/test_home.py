"""Shared settings, Spicy consent, and live updates between the two phones."""

from fastapi.testclient import TestClient

from app.main import app
from app.mix import categories_in_play
from helpers import OWNER, error_code, paired

# ── The hat ───────────────────────────────────────────────────────────────────


def test_mix_rules():
    normal = {"categories": ["cozy", "silly"], "random": False, "excluded": []}
    assert categories_in_play(normal, spicy_both=False) == ["cozy", "silly"]
    assert categories_in_play(normal, spicy_both=True) == ["cozy", "silly", "spicy"]

    rnd = {"categories": ["cozy"], "random": True, "excluded": ["big", "memories"]}
    assert categories_in_play(rnd, spicy_both=False) == ["cozy", "silly", "sweet", "future"]
    # Spicy can't sneak in through the hat: only the two switches decide it.
    assert "spicy" not in categories_in_play({"categories": ["spicy"], "random": False, "excluded": []}, False)


# ── Settings ──────────────────────────────────────────────────────────────────


async def test_default_home(make_client, outbox):
    me, her = await paired(make_client, outbox)
    h = (await me.get("/api/home")).json()
    assert h["settings"] == {"depth": "light", "categories": ["cozy", "silly", "sweet"], "random": False, "excluded": []}
    assert h["in_play"] == ["cozy", "silly", "sweet"]
    assert h["spicy_me"] is False and h["spicy_them"] is False
    me_id = (await me.get("/api/auth/me")).json()["id"]
    assert h["turn_user_id"] == me_id  # the owner draws first


async def test_settings_are_shared(make_client, outbox):
    me, her = await paired(make_client, outbox)
    r = await her.patch("/api/settings", json={"depth": "deep", "categories": ["future", "cozy", "cozy"]})
    assert r.status_code == 200, r.text
    assert r.json()["categories"] == ["cozy", "future"]  # de-duplicated, in hat order
    seen = (await me.get("/api/home")).json()
    assert seen["settings"]["depth"] == "deep"
    her_id = (await her.get("/api/auth/me")).json()["id"]
    assert seen["settings_updated_by"] == her_id


async def test_hat_cannot_be_empty(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    assert error_code(await me.patch("/api/settings", json={"categories": []})) == "empty_hat"
    every = ["cozy", "silly", "sweet", "big", "memories", "future"]
    r = await me.patch("/api/settings", json={"random": True, "excluded": every})
    assert error_code(r) == "empty_hat"


async def test_spicy_is_not_a_hat_category(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    assert (await me.patch("/api/settings", json={"categories": ["spicy"]})).status_code == 422
    assert (await me.patch("/api/settings", json={"depth": "abyss"})).status_code == 422


async def test_random_starts_with_no_exclusions(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    await me.patch("/api/settings", json={"random": True})
    await me.patch("/api/settings", json={"excluded": ["big"]})
    assert (await me.get("/api/home")).json()["in_play"] == ["cozy", "silly", "sweet", "memories", "future"]
    # Off and on again: the old exclusion is gone.
    await me.patch("/api/settings", json={"random": False})
    r = await me.patch("/api/settings", json={"random": True})
    assert r.json()["excluded"] == []


# ── Spicy needs both ──────────────────────────────────────────────────────────


async def test_spicy_needs_both(make_client, outbox):
    me, her = await paired(make_client, outbox)
    await me.put("/api/me/spicy", json={"on": True})
    mine, hers = (await me.get("/api/home")).json(), (await her.get("/api/home")).json()
    assert mine["spicy_me"] and not mine["spicy_them"] and "spicy" not in mine["in_play"]
    assert hers["spicy_them"] and not hers["spicy_me"]

    await her.put("/api/me/spicy", json={"on": True})
    assert "spicy" in (await me.get("/api/home")).json()["in_play"]

    await me.put("/api/me/spicy", json={"on": False})  # either one can switch it off again
    assert "spicy" not in (await her.get("/api/home")).json()["in_play"]


# ── Live updates ──────────────────────────────────────────────────────────────
# Starlette's test client runs every WebSocket on its own event loop, so a broadcast from one
# simulated phone to another's socket can't be delivered in a test (it waits forever). So:
#   1. the hub's routing is tested with stand-in sockets,
#   2. each change is checked to broadcast the right message (hub calls recorded),
#   3. a real socket is opened once, alone, to check sign-in on the live connection.


def _sign_in_sync(client: TestClient, outbox, email: str, monkeypatch) -> None:
    """Sign an existing user in on another 'phone' (sync client, for the WebSocket test)."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "code_resend_seconds", 0)
    client.post("/api/auth/code", json={"email": email})
    r = client.post("/api/auth/verify", json={"email": email, "code": outbox[email][-1]})
    assert r.json()["status"] == "signed_in", r.text


async def _make_pair(make_client, outbox):
    await paired(make_client, outbox)


class FakeSocket:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, msg):
        self.sent.append(msg)


async def test_hub_routes_to_the_right_people():
    import uuid

    from app.live import Hub

    hub = Hub()
    a, b = uuid.uuid4(), uuid.uuid4()
    a_phone, a_laptop, b_phone = FakeSocket(), FakeSocket(), FakeSocket()
    hub.add(a, a_phone)
    hub.add(a, a_laptop)
    hub.add(b, b_phone)
    assert hub.online(a) and hub.online(b)

    await hub.send(a, {"type": "x"})
    assert a_phone.sent == a_laptop.sent == [{"type": "x"}] and b_phone.sent == []

    await hub.to_users([a, b, None], {"type": "y"})
    assert b_phone.sent == [{"type": "y"}] and len(a_phone.sent) == 2

    hub.remove(a, a_phone)
    assert hub.online(a)  # still open on the laptop
    hub.remove(a, a_laptop)
    assert not hub.online(a)


async def test_changes_are_broadcast(make_client, outbox, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    her_id = (await her.get("/api/auth/me")).json()["id"]
    sent: list[dict] = []

    async def record(message):
        sent.append(message)

    monkeypatch.setattr(live.hub, "to_pair", record)

    await her.patch("/api/settings", json={"depth": "medium"})
    assert sent[-1]["type"] == "settings" and sent[-1]["settings"]["depth"] == "medium" and sent[-1]["by"] == her_id

    await her.put("/api/me/spicy", json={"on": True})
    assert sent[-1] == {"type": "spicy", "user_id": her_id, "on": True}

    await her.patch("/api/me", json={"display_name": "Ama A."})
    assert sent[-1]["type"] == "profile" and sent[-1]["display_name"] == "Ama A."


def test_live_socket_says_hello(make_client, outbox, monkeypatch):
    import asyncio

    asyncio.run(_make_pair(make_client, outbox))
    phone = TestClient(app)
    _sign_in_sync(phone, outbox, OWNER, monkeypatch)
    with phone.websocket_connect("/api/ws") as ws:
        assert ws.receive_json() == {"type": "hello", "partner_online": False, "partner_ready": False, "partner_where": ""}
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_live_needs_a_session():
    c = TestClient(app)
    try:
        with c.websocket_connect("/api/ws") as ws:
            ws.receive_json()
        raised = False
    except Exception:
        raised = True
    assert raised
