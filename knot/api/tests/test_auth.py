"""The whole sign-in story, end to end, against a real Postgres."""

import httpx
import pytest

from app.config import get_settings

OWNER = "baron@example.com"
HER = "her@example.com"
STRANGER = "someone@example.com"


async def get_code(client: httpx.AsyncClient, outbox, email: str) -> str:
    r = await client.post("/api/auth/code", json={"email": email})
    assert r.status_code == 200, r.text
    assert outbox[email], f"no code was sent to {email}"
    return outbox[email][-1]


async def verify(client: httpx.AsyncClient, email: str, code: str) -> httpx.Response:
    return await client.post("/api/auth/verify", json={"email": email, "code": code})


async def sign_up_owner(client, outbox) -> dict:
    code = await get_code(client, outbox, OWNER)
    r = await verify(client, OWNER, code)
    assert r.json()["status"] == "new_owner"
    r = await client.post("/api/auth/join", json={"ticket": r.json()["ticket"], "display_name": "Baron"})
    assert r.status_code == 200, r.text
    return r.json()


async def make_invite(owner_client) -> str:
    r = await owner_client.post("/api/invites")
    assert r.status_code == 200, r.text
    return r.json()["code"]


async def sign_up_partner(client, outbox, invite: str, email: str = HER, name: str = "Ama") -> httpx.Response:
    code = await get_code(client, outbox, email)
    r = await verify(client, email, code)
    assert r.json()["status"] == "needs_pairing"
    return await client.post(
        "/api/auth/join", json={"ticket": r.json()["ticket"], "display_name": name, "invite_code": invite}
    )


def error_code(r: httpx.Response) -> str:
    return r.json()["detail"]["code"]


# ── The happy path ────────────────────────────────────────────────────────────


async def test_full_pairing_flow(make_client, outbox):
    me_phone, her_phone, stranger_phone = make_client(), make_client(), make_client()

    owner = await sign_up_owner(me_phone, outbox)
    assert owner["role"] == "owner" and owner["display_name"] == "Baron"
    assert owner["pair_complete"] is False and owner["partner"] is None

    invite = await make_invite(me_phone)
    assert invite.startswith("TIE-")

    # She types it lower-case without the dash: still works.
    code = await get_code(her_phone, outbox, HER)
    r = await verify(her_phone, HER, code)
    ticket = r.json()["ticket"]
    sloppy = invite.lower().replace("-", " ")
    assert (await her_phone.post("/api/auth/check-invite", json={"ticket": ticket, "invite_code": sloppy})).json() == {
        "ok": True
    }
    r = await her_phone.post(
        "/api/auth/join", json={"ticket": ticket, "display_name": "  Ama  ", "invite_code": sloppy}
    )
    assert r.status_code == 200, r.text
    her = r.json()
    assert her["role"] == "partner" and her["display_name"] == "Ama"
    assert her["partner"]["display_name"] == "Baron"

    owner_now = (await me_phone.get("/api/auth/me")).json()
    assert owner_now["pair_complete"] is True and owner_now["partner"]["display_name"] == "Ama"

    # A third person: same response, but no email ever goes out.
    r = await stranger_phone.post("/api/auth/code", json={"email": STRANGER})
    assert r.status_code == 200
    assert STRANGER not in outbox


async def test_returning_user_signs_straight_in(make_client, outbox, monkeypatch):
    await sign_up_owner(make_client(), outbox)
    # Signing in again right after sign-up would hit the 60s resend cooldown (no new email).
    monkeypatch.setattr(get_settings(), "code_resend_seconds", 0)
    new_phone = make_client()
    r = await verify(new_phone, OWNER, await get_code(new_phone, outbox, OWNER))
    assert r.json()["status"] == "signed_in"
    assert r.json()["me"]["display_name"] == "Baron"
    assert (await new_phone.get("/api/auth/me")).status_code == 200


# ── Who gets a code ───────────────────────────────────────────────────────────


async def test_nobody_but_owner_gets_a_code_before_setup(make_client, outbox):
    c = make_client()
    r1 = await c.post("/api/auth/code", json={"email": STRANGER})
    r2 = await c.post("/api/auth/code", json={"email": OWNER})
    # Identical answers, so the response can't be used to probe which emails are allowed.
    assert r1.json() == r2.json()
    assert STRANGER not in outbox and OWNER in outbox


async def test_no_codes_for_new_people_without_an_open_invite(make_client, outbox):
    await sign_up_owner(make_client(), outbox)
    await make_client().post("/api/auth/code", json={"email": HER})
    assert HER not in outbox  # owner hasn't made a pairing code yet


async def test_email_is_case_insensitive(make_client, outbox):
    c = make_client()
    await c.post("/api/auth/code", json={"email": "Baron@Example.COM"})
    code = outbox[OWNER][-1]
    assert (await verify(c, "BARON@example.com", code)).json()["status"] == "new_owner"


# ── Code rules ────────────────────────────────────────────────────────────────


async def test_wrong_code_limits(make_client, outbox):
    c = make_client()
    code = await get_code(c, outbox, OWNER)
    wrong = "000000" if code != "000000" else "111111"
    max_attempts = get_settings().code_max_attempts

    for left in range(max_attempts - 1, 0, -1):
        r = await verify(c, OWNER, wrong)
        assert error_code(r) == "code_wrong" and r.json()["detail"]["attempts_left"] == left
    r = await verify(c, OWNER, wrong)
    assert error_code(r) == "code_expired"  # burned
    # Even the right code no longer works.
    assert error_code(await verify(c, OWNER, code)) == "code_wrong"


async def test_resend_cooldown_and_newest_code_wins(make_client, outbox, monkeypatch):
    c = make_client()
    await c.post("/api/auth/code", json={"email": OWNER})
    await c.post("/api/auth/code", json={"email": OWNER})
    assert len(outbox[OWNER]) == 1  # second request inside 60s sent nothing

    monkeypatch.setattr(get_settings(), "code_resend_seconds", 0)
    await c.post("/api/auth/code", json={"email": OWNER})
    old, new = outbox[OWNER][0], outbox[OWNER][-1]
    if old != new:
        assert error_code(await verify(c, OWNER, old)) == "code_wrong"
    assert (await verify(c, OWNER, new)).json()["status"] == "new_owner"


async def test_code_is_single_use(make_client, outbox):
    c = make_client()
    code = await get_code(c, outbox, OWNER)
    assert (await verify(c, OWNER, code)).status_code == 200
    assert error_code(await verify(c, OWNER, code)) == "code_wrong"


# ── Pairing rules ─────────────────────────────────────────────────────────────


async def test_pair_closes_after_two(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    invite = await make_invite(me_phone)
    assert (await sign_up_partner(make_client(), outbox, invite)).status_code == 200

    # No more invites, and the old one is spent.
    assert error_code(await me_phone.post("/api/invites")) == "pair_full"
    assert STRANGER not in outbox
    await make_client().post("/api/auth/code", json={"email": STRANGER})
    assert STRANGER not in outbox


async def test_new_invite_cancels_the_old_one(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    first = await make_invite(me_phone)
    second = await make_invite(me_phone)
    r = await sign_up_partner(make_client(), outbox, first)
    assert error_code(r) == "invite_invalid"
    # A different address, because the same one would still be inside the 60s resend cooldown.
    r = await sign_up_partner(make_client(), outbox, second, email="her.again@example.com")
    assert r.status_code == 200


async def test_revoked_invite_stops_working(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    invite = await make_invite(me_phone)
    her = make_client()
    code = await get_code(her, outbox, HER)  # sent while the invite is open
    assert (await me_phone.delete("/api/invites")).status_code == 204
    ticket = (await verify(her, HER, code)).json()["ticket"]
    r = await her.post("/api/auth/check-invite", json={"ticket": ticket, "invite_code": invite})
    assert error_code(r) == "invite_invalid"


async def test_join_needs_an_invite(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    await make_invite(me_phone)
    r = await sign_up_partner(make_client(), outbox, "TIE-WRONG")
    assert error_code(r) == "invite_invalid"


async def test_pairing_guesses_are_limited(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    await make_invite(me_phone)
    her = make_client()
    ticket = (await verify(her, HER, await get_code(her, outbox, HER))).json()["ticket"]
    codes = []
    for _ in range(6):
        r = await her.post("/api/auth/check-invite", json={"ticket": ticket, "invite_code": "TIE-AAAAA"})
        codes.append(error_code(r))
    assert codes[:5] == ["invite_invalid"] * 5 and codes[5] == "slow_down"


async def test_partner_cannot_invite(make_client, outbox):
    me_phone = make_client()
    await sign_up_owner(me_phone, outbox)
    her = make_client()
    await sign_up_partner(her, outbox, await make_invite(me_phone))
    assert error_code(await her.post("/api/invites")) == "not_owner"


async def test_tampered_ticket_is_rejected(make_client, outbox):
    c = make_client()
    ticket = (await verify(c, OWNER, await get_code(c, outbox, OWNER))).json()["ticket"]
    body, sig = ticket.split(".")
    r = await c.post("/api/auth/join", json={"ticket": body + ".x" + sig[1:], "display_name": "Baron"})
    assert error_code(r) == "ticket_expired"


# ── Sessions and profile ──────────────────────────────────────────────────────


async def test_logout_and_bad_cookie(make_client, outbox):
    c = make_client()
    await sign_up_owner(c, outbox)
    assert (await c.post("/api/auth/logout")).status_code == 204
    assert error_code(await c.get("/api/auth/me")) == "not_signed_in"

    r = await make_client().get("/api/auth/me", headers={"Cookie": "knot=made-up-token"})
    assert error_code(r) == "session_expired"


async def test_change_name_and_theme(make_client, outbox):
    c = make_client()
    await sign_up_owner(c, outbox)
    r = await c.patch(
        "/api/me",
        json={"display_name": "B", "theme": {"mode": "candle", "preset": "tide", "base_hue": 225, "accent_hue": 190}},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "B" and r.json()["theme"]["preset"] == "tide"
    assert (await c.patch("/api/me", json={"display_name": "   "})).status_code == 422


@pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", ""])
async def test_code_format_is_checked(make_client, bad):
    r = await make_client().post("/api/auth/verify", json={"email": OWNER, "code": bad})
    assert r.status_code == 422
