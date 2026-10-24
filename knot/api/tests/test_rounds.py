"""The game: draw, answer, seal, pull, pass, retire, turns, and nothing kept afterwards.

The test pack (sample/test-000.json) is small, so each test narrows the mix to land on a
known card type:  cozy+deep → a "Just you" card · sweet+deep → a "both" card ·
big+deep → a Guess card.
"""

import base64
import os
from datetime import timedelta

from sqlalchemy import text

from app.db import SessionLocal
from app.deps import now
from app.tools.import_pack import import_pack
from helpers import error_code, paired

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample", "test-000.json")


def sealed(n: int = 40) -> dict:
    return {
        "ciphertext": base64.b64encode(os.urandom(n)).decode(),
        "nonce": base64.b64encode(os.urandom(12)).decode(),
        "key_version": 0,
    }


async def mix(phone, category: str, depth: str):
    r = await phone.patch("/api/settings", json={"categories": [category], "depth": depth, "random": False})
    assert r.status_code == 200, r.text


async def ids(me, her):
    return (await me.get("/api/auth/me")).json()["id"], (await her.get("/api/auth/me")).json()["id"]


async def count(sql: str) -> int:
    async with SessionLocal() as db:
        return (await db.execute(text(sql))).scalar()


# ── Drawing ───────────────────────────────────────────────────────────────────


async def test_draw_both_phones_see_the_same_card(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    r = await me.post("/api/rounds")
    assert r.status_code == 200, r.text
    rnd = r.json()
    assert rnd["question"]["type"] == "both" and rnd["question"]["text"]
    assert rnd["i_answer"] and rnd["partner_answers"] and not rnd["i_sealed"]

    theirs = (await her.get("/api/rounds/current")).json()["round"]
    assert theirs["id"] == rnd["id"] and theirs["question"]["text"] == rnd["question"]["text"]


async def test_one_round_at_a_time_and_turns(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    await mix(me, "silly", "light")
    # Owner draws first. Her phone isn't connected (offline), so she *could* draw to leave
    # one sealed — but there's already a card on the table.
    first = (await me.post("/api/rounds")).json()
    assert error_code(await her.post("/api/rounds")) == "round_open"

    await me.post(f"/api/rounds/{first['id']}/pass")
    home = (await me.get("/api/home")).json()
    _, her_id = await ids(me, her)
    assert home["turn_user_id"] == her_id  # the turn passes


async def test_spicy_only_when_both_say_yes(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    await mix(me, "cozy", "deep")  # one cozy card at this depth, plus one spicy card
    await me.put("/api/me/spicy", json={"on": True})  # only him so far

    first = (await me.post("/api/rounds")).json()
    assert first["question"]["category"] == "cozy"
    await me.post(f"/api/rounds/{first['id']}/pass")
    assert error_code(await me.post("/api/rounds")) == "empty"  # spicy still isn't in play

    await her.put("/api/me/spicy", json={"on": True})  # now both
    r = await me.post("/api/rounds")
    assert r.status_code == 200 and r.json()["question"]["category"] == "spicy"


async def test_empty_mix_and_reshuffle(make_client, outbox, bank):
    me, _ = await paired(make_client, outbox)
    await mix(me, "cozy", "deep")  # exactly one card in the test pack
    r = (await me.post("/api/rounds")).json()
    await me.post(f"/api/rounds/{r['id']}/pass")
    # Turn passed to her, but she's offline, so he can still draw (to leave one for her).
    assert error_code(await me.post("/api/rounds")) == "empty"
    assert (await me.post("/api/rounds/reshuffle")).json()["shuffled_back"] == 1
    assert (await me.post("/api/rounds")).status_code == 200


# ── Answering and revealing ───────────────────────────────────────────────────


async def test_full_round_then_nothing_is_kept(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    me_id, her_id = await ids(me, her)
    await mix(me, "sweet", "deep")
    rid = (await me.post("/api/rounds")).json()["id"]

    r = await me.post(f"/api/rounds/{rid}/seal", json=sealed())
    assert r.json()["state"] == "open" and r.json()["i_sealed"]
    assert error_code(await me.post(f"/api/rounds/{rid}/seal", json=sealed())) == "already_sealed"
    assert error_code(await me.post(f"/api/rounds/{rid}/pull", json={})) == "not_ready"

    r = await her.post(f"/api/rounds/{rid}/seal", json=sealed())
    assert r.json()["state"] == "ready"

    # He pulls while she's "away" (no live connection in these tests): he reads it now.
    r = (await me.post(f"/api/rounds/{rid}/pull", json={})).json()
    assert r["revealed"] and len(r["answers"]) == 2
    assert await count("SELECT count(*) FROM rounds") == 1  # waits for her pull

    # She pulls: revealed to her too, and then it's all gone.
    r = (await her.post(f"/api/rounds/{rid}/pull", json={})).json()
    assert r["revealed"] and {a["user_id"] for a in r["answers"]} == {me_id, her_id}
    assert await count("SELECT count(*) FROM rounds") == 0
    assert await count("SELECT count(*) FROM sealed_answers") == 0
    assert await count("SELECT count(*) FROM drawn_questions") == 1  # only the question id remains
    assert (await me.get("/api/home")).json()["turn_user_id"] == her_id


async def test_just_you_card(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    await mix(me, "cozy", "deep")
    rnd = (await me.post("/api/rounds")).json()
    assert rnd["question"]["type"] == "self" and rnd["i_answer"] and not rnd["partner_answers"]
    assert error_code(await her.post(f"/api/rounds/{rnd['id']}/seal", json=sealed())) == "not_yours"
    r = await me.post(f"/api/rounds/{rnd['id']}/seal", json=sealed())
    assert r.json()["state"] == "ready"  # only the writer needs to seal


async def test_guess_card_roles(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    _, her_id = await ids(me, her)
    await mix(me, "big", "deep")
    pool = []
    for _ in range(3):
        r = (await me.post("/api/rounds")).json()
        pool.append(r)
        if r["question"]["type"] == "guess":
            break
        await me.post(f"/api/rounds/{r['id']}/pass")
    g = pool[-1]
    assert g["question"]["type"] == "guess" and "{p}" in g["question"]["text"]
    assert g["subject_id"] == her_id  # the drawer guesses about the other person


async def test_stale_key_is_refused(make_client, outbox, bank):
    me, _ = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    rid = (await me.post("/api/rounds")).json()["id"]
    assert error_code(await me.post(f"/api/rounds/{rid}/seal", json={**sealed(), "key_version": 7})) == "stale_key"


async def test_answer_size_is_limited(make_client, outbox, bank):
    me, _ = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    rid = (await me.post("/api/rounds")).json()["id"]
    assert (await me.post(f"/api/rounds/{rid}/seal", json=sealed(9000))).status_code == 422


# ── Passing, retiring, expiry ─────────────────────────────────────────────────


async def test_pass_deletes_answers_unread(make_client, outbox, bank):
    me, her = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    rid = (await me.post("/api/rounds")).json()["id"]
    await me.post(f"/api/rounds/{rid}/seal", json=sealed())
    assert (await her.post(f"/api/rounds/{rid}/pass")).status_code == 200
    assert await count("SELECT count(*) FROM sealed_answers") == 0
    assert (await me.get("/api/rounds/current")).json()["round"] is None


async def test_retire_takes_a_question_out_for_good(make_client, outbox, bank):
    me, _ = await paired(make_client, outbox)
    await mix(me, "cozy", "deep")
    rnd = (await me.post("/api/rounds")).json()
    await me.post(f"/api/rounds/{rnd['id']}/retire")
    await me.post("/api/rounds/reshuffle")
    assert error_code(await me.post("/api/rounds")) == "empty"  # even after reshuffling
    assert await count(f"SELECT count(*) FROM questions WHERE id = '{rnd['question']['id']}' AND retired_at IS NOT NULL") == 1


async def test_expired_round_is_let_go(make_client, outbox, bank):
    me, _ = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    rid = (await me.post("/api/rounds")).json()["id"]
    async with SessionLocal() as db:
        await db.execute(text("UPDATE rounds SET expires_at = :t"), {"t": now() - timedelta(minutes=1)})
        await db.commit()
    assert (await me.get("/api/rounds/current")).json()["round"] is None
    assert error_code(await me.post(f"/api/rounds/{rid}/seal", json=sealed())) == "round_gone"
    await mix(me, "future", "deep")
    assert (await me.post("/api/rounds")).status_code == 200  # doesn't block a new draw

    from app.purge import purge_once

    await purge_once()


# ── Importing ─────────────────────────────────────────────────────────────────


async def test_importing_twice_changes_nothing(bank, capsys):
    assert await import_pack(__import__("pathlib").Path(SAMPLE)) == 0
    assert "already imported" in capsys.readouterr().out
    assert await count("SELECT count(*) FROM questions") == 42


# ── Both here: "I'm ready" ────────────────────────────────────────────────────


async def test_both_ready_deals_one_card_to_both(make_client, outbox, bank, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    await mix(me, "sweet", "deep")
    monkeypatch.setattr(live.hub, "online", lambda user_id: True)  # pretend both apps are open

    # Drawing alone isn't how it works when you're both here.
    assert error_code(await me.post("/api/rounds")) == "use_ready"

    r = (await her.post("/api/rounds/ready", json={"ready": True})).json()
    assert r == {"drawn": False, "empty": False, "round": None, "ready_me": True, "ready_them": False}
    assert (await me.get("/api/home")).json()["ready_them"] is True

    r = (await me.post("/api/rounds/ready", json={"ready": True})).json()
    assert r["drawn"] and r["round"]["question"]["type"] == "both"
    theirs = (await her.get("/api/rounds/current")).json()["round"]
    assert theirs["id"] == r["round"]["id"]
    assert (await me.get("/api/home")).json()["ready_me"] is False  # ready resets after a deal


async def test_ready_can_be_taken_back(make_client, outbox, bank, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    monkeypatch.setattr(live.hub, "online", lambda user_id: True)
    await her.post("/api/rounds/ready", json={"ready": True})
    await her.post("/api/rounds/ready", json={"ready": False})
    r = (await me.post("/api/rounds/ready", json={"ready": True})).json()
    assert r["drawn"] is False and r["ready_them"] is False


async def test_drawer_alternates_between_deals(make_client, outbox, bank, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    me_id, her_id = await ids(me, her)
    await mix(me, "silly", "light")
    monkeypatch.setattr(live.hub, "online", lambda user_id: True)

    drawers = []
    for _ in range(2):
        await me.post("/api/rounds/ready", json={"ready": True})
        rnd = (await her.post("/api/rounds/ready", json={"ready": True})).json()["round"]
        drawers.append(rnd["drawn_by"])
        await me.post(f"/api/rounds/{rnd['id']}/pass")
    assert drawers == [me_id, her_id]


async def test_both_ready_on_an_empty_hat(make_client, outbox, bank, monkeypatch):
    from app import live

    me, her = await paired(make_client, outbox)
    await mix(me, "cozy", "deep")
    await me.post("/api/rounds")  # (both offline here) take the only card
    rid = (await me.get("/api/rounds/current")).json()["round"]["id"]
    await me.post(f"/api/rounds/{rid}/pass")

    monkeypatch.setattr(live.hub, "online", lambda user_id: True)
    await me.post("/api/rounds/ready", json={"ready": True})
    r = (await her.post("/api/rounds/ready", json={"ready": True})).json()
    assert r["drawn"] is False and r["empty"] is True
