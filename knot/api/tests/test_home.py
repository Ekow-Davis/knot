"""Shared settings, Spicy consent, and live updates between the two phones."""

from fastapi.testclient import TestClient

from app.main import app
from app.mix import categories_in_play
from helpers import HER, OWNER, error_code, paired

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


# ── Live: two phones over WebSockets ──────────────────────────────────────────


def _sign_in_sync(client: TestClient, outbox, email: str, monkeypatch) -> None:
    """Sign an existing user in on another 'phone' (sync client, for WebSocket tests)."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "code_resend_seconds", 0)
    client.post("/api/auth/code", json={"email": email})
    r = client.post("/api/auth/verify", json={"email": email, "code": outbox[email][-1]})
    assert r.json()["status"] == "signed_in", r.text


async def _make_pair(make_client, outbox):
    await paired(make_client, outbox)


def test_live_presence_and_settings(make_client, outbox, monkeypatch):
    import asyncio

    # Create the pair with the async helpers, then sign both in on sync clients.
    asyncio.run(_make_pair(make_client, outbox))
    my_phone, her_phone = TestClient(app), TestClient(app)
    _sign_in_sync(my_phone, outbox, OWNER, monkeypatch)
    _sign_in_sync(her_phone, outbox, HER, monkeypatch)

    with my_phone.websocket_connect("/api/ws") as mine:
        assert mine.receive_json() == {"type": "hello", "partner_online": False}

        with her_phone.websocket_connect("/api/ws") as hers:
            assert hers.receive_json() == {"type": "hello", "partner_online": True}
            assert mine.receive_json() == {"type": "presence", "online": True}

            # She changes depth: both phones hear about it.
            her_phone.patch("/api/settings", json={"depth": "medium"})
            for ws in (mine, hers):
                msg = ws.receive_json()
                assert msg["type"] == "settings" and msg["settings"]["depth"] == "medium"

            # She turns Spicy on.
            her_phone.put("/api/me/spicy", json={"on": True})
            assert mine.receive_json()["type"] == "spicy"
            hers.receive_json()

            hers.send_json({"type": "ping"})
            assert hers.receive_json() == {"type": "pong"}

        # She closed the app.
        assert mine.receive_json() == {"type": "presence", "online": False}


def test_live_needs_a_session():
    c = TestClient(app)
    try:
        with c.websocket_connect("/api/ws") as ws:
            ws.receive_json()
        raised = False
    except Exception:
        raised = True
    assert raised
