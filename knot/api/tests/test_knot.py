"""Tying, reading and retying the knot."""

import base64
import os

from sqlalchemy import text

from app.db import SessionLocal
from helpers import error_code, paired, sign_up_owner


def b64(n: int) -> str:
    return base64.b64encode(os.urandom(n)).decode()


def knot_body(**over) -> dict:
    body = {
        "kdf_salt": b64(16),
        "kdf_params": {"alg": "argon2id", "m": 65536, "t": 3, "p": 1, "v": 1},
        "key_check": b64(29),  # 13-byte check string + 16-byte GCM tag
        "key_check_nonce": b64(12),
    }
    body.update(over)
    return body


async def test_tie_once_and_both_phones_see_it(make_client, outbox):
    me, her = await paired(make_client, outbox)
    r = await me.get("/api/knot")
    assert r.json() == {
        "tied": False,
        "key_version": 0,
        "kdf_salt": None,
        "kdf_params": None,
        "key_check": None,
        "key_check_nonce": None,
    }

    body = knot_body()
    r = await me.post("/api/knot", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["tied"] is True and r.json()["key_version"] == 1

    theirs = (await her.get("/api/knot")).json()
    assert theirs["kdf_salt"] == body["kdf_salt"]
    assert theirs["key_check"] == body["key_check"]
    assert theirs["kdf_params"]["m"] == 65536


async def test_second_tie_gets_the_existing_knot(make_client, outbox):
    me, her = await paired(make_client, outbox)
    first = knot_body()
    await me.post("/api/knot", json=first)
    r = await her.post("/api/knot", json=knot_body())
    assert error_code(r) == "already_tied"
    # Her phone is handed the real knot so it can switch to "enter the phrase".
    assert r.json()["detail"]["knot"]["kdf_salt"] == first["kdf_salt"]


async def test_owner_can_tie_before_partner_joins(make_client, outbox):
    me = make_client()
    await sign_up_owner(me, outbox)
    assert (await me.post("/api/knot", json=knot_body())).status_code == 200


async def test_retie_bumps_version_and_clears_sealed_rounds(make_client, outbox):
    me, her = await paired(make_client, outbox)
    await me.post("/api/knot", json=knot_body())

    # Put a sealed round in place, as Session 5 will.
    async with SessionLocal() as db:
        uid = (await db.execute(text("SELECT id FROM users LIMIT 1"))).scalar()
        await db.execute(text("INSERT INTO question_packs(id, checksum, question_count) VALUES ('t-001','x',1)"))
        await db.execute(
            text(
                "INSERT INTO questions(id,pack_id,type,depth,category,payload,payload_nonce) "
                "VALUES ('t-001-0001','t-001','both','light','cozy','\\x00','\\x00')"
            )
        )
        rid = (
            await db.execute(
                text(
                    "INSERT INTO rounds(question_id, drawn_by, expires_at) "
                    "VALUES ('t-001-0001', :u, now() + interval '1 day') RETURNING id"
                ),
                {"u": uid},
            )
        ).scalar()
        await db.execute(
            text("INSERT INTO sealed_answers(round_id,user_id,ciphertext,nonce,key_version) VALUES (:r,:u,'\\x01','\\x02',1)"),
            {"r": rid, "u": uid},
        )
        await db.commit()

    # Retie against a stale version is refused.
    r = await her.put("/api/knot", json=knot_body(expected_version=0))
    assert error_code(r) == "version_changed"

    new = knot_body(expected_version=1)
    r = await her.put("/api/knot", json=new)
    assert r.status_code == 200, r.text
    assert r.json()["key_version"] == 2 and r.json()["kdf_salt"] == new["kdf_salt"]

    async with SessionLocal() as db:
        assert (await db.execute(text("SELECT count(*) FROM rounds"))).scalar() == 0
        assert (await db.execute(text("SELECT count(*) FROM sealed_answers"))).scalar() == 0


async def test_retie_needs_a_knot(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    assert error_code(await me.put("/api/knot", json=knot_body())) == "not_tied"


async def test_bad_knot_values_are_rejected(make_client, outbox):
    me, _ = await paired(make_client, outbox)
    bad = [
        knot_body(kdf_salt=b64(15)),  # salt must be 16 bytes
        knot_body(key_check_nonce=b64(8)),  # nonce must be 12 bytes
        knot_body(key_check="not base64!"),
        knot_body(kdf_params={"alg": "argon2id", "m": 2_000_000, "t": 3, "p": 1, "v": 1}),  # 2 GB: no
        knot_body(kdf_params={"alg": "pbkdf2", "m": 65536, "t": 3, "p": 1, "v": 1}),
    ]
    for body in bad:
        assert (await me.post("/api/knot", json=body)).status_code == 422, body
    assert (await me.get("/api/knot")).json()["tied"] is False


async def test_knot_needs_sign_in(make_client):
    assert error_code(await make_client().get("/api/knot")) == "not_signed_in"
