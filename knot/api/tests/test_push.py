"""Notifications: subscribing, who gets told what, and forgetting dead subscriptions.
Nothing is actually sent: the sender is replaced with a recorder."""

import uuid

from sqlalchemy import text

from app import push
from app.config import get_settings
from app.db import SessionLocal
from helpers import error_code, paired

SUB = {
    "endpoint": "https://web.push.apple.com/QGzp-example",
    "keys": {"p256dh": "BOrk" + "x" * 80, "auth": "authsecret123456"},
}


def vapid_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "vapid_public_key", "BPublicKeyForTests" + "x" * 60)
    monkeypatch.setattr(s, "vapid_private_key", "private-for-tests")


def record_notifications(monkeypatch) -> list[tuple]:
    sent: list[tuple] = []
    from app.routes import rounds

    monkeypatch.setattr(rounds, "notify_later", lambda uid, title, body, **kw: sent.append((str(uid), title, body)))
    return sent


async def test_key_needs_setup(make_client, outbox, monkeypatch):
    me, _ = await paired(make_client, outbox)
    assert error_code(await me.get("/api/push/key")) == "push_off"
    vapid_on(monkeypatch)
    assert (await me.get("/api/push/key")).json()["key"].startswith("BPublicKey")


async def test_subscribe_and_unsubscribe(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    assert (await me.post("/api/push/subscribe", json=SUB)).status_code == 204
    assert (await me.post("/api/push/subscribe", json=SUB)).status_code == 204  # same phone again: no duplicate
    async with SessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM push_subscriptions"))).scalar() == 1
    await me.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]})
    async with SessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM push_subscriptions"))).scalar() == 0


async def test_only_https_endpoints(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    bad = {**SUB, "endpoint": "http://evil.example/collect"}
    assert (await me.post("/api/push/subscribe", json=bad)).status_code == 422


async def test_tug_notifies_only_when_away(make_client, outbox, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    her_id = (await her.get("/api/auth/me")).json()["id"]
    sent = record_notifications(monkeypatch)

    await me.post("/api/rounds/tug")  # she's away (no live connection in tests)
    assert sent == [(her_id, "Baron", "gave the rope a little tug.")]

    monkeypatch.setattr(live.hub, "online", lambda user_id: True)
    from app.routes import rounds

    rounds.tugs_per_user.reset()
    await me.post("/api/rounds/tug")  # she's here: the live toast is enough
    assert len(sent) == 1

    live.hub.hidden.add(uuid.UUID(her_id))  # connected, but the app is in the background
    rounds.tugs_per_user.reset()
    await me.post("/api/rounds/tug")
    assert len(sent) == 2


async def test_left_question_and_answer_notify(make_client, outbox, bank, monkeypatch):
    me, her = await paired(make_client, outbox)
    me_id, her_id = (await me.get("/api/auth/me")).json()["id"], (await her.get("/api/auth/me")).json()["id"]
    sent = record_notifications(monkeypatch)
    await me.patch("/api/settings", json={"categories": ["sweet"], "depth": "deep"})

    rid = (await me.post("/api/rounds")).json()["id"]  # drawn while she's away
    assert sent == []  # nothing until there's actually something sealed for her

    import base64
    import os

    def sealed():
        return {
            "ciphertext": base64.b64encode(os.urandom(40)).decode(),
            "nonce": base64.b64encode(os.urandom(12)).decode(),
            "key_version": 0,
        }

    await me.post(f"/api/rounds/{rid}/seal", json=sealed())
    assert sent[-1] == (her_id, "Baron", "left you a sealed question. It keeps for 24 hours.")
    await her.post(f"/api/rounds/{rid}/seal", json=sealed())
    assert sent[-1] == (me_id, "Ama", "answered. Your end of the rope is waiting.")


async def test_dead_subscriptions_are_forgotten(make_client, outbox, monkeypatch):
    me, _ = await paired(make_client, outbox)
    vapid_on(monkeypatch)
    await me.post("/api/push/subscribe", json=SUB)
    other = {**SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/abc"}
    await me.post("/api/push/subscribe", json=other)
    me_id = uuid.UUID((await me.get("/api/auth/me")).json()["id"])

    # Apple says the first is gone (410); Google accepts the second (201).
    monkeypatch.setattr(push, "_send_one", lambda sub, payload: 410 if "apple" in sub.endpoint else 201)
    assert await push.notify(me_id, "Ama", "gave the rope a little tug.", tag="tug") == 1
    async with SessionLocal() as db:
        left = (await db.execute(text("SELECT endpoint FROM push_subscriptions"))).scalars().all()
    assert left == [other["endpoint"]]
