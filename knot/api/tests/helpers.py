"""Shared test helpers: sign people up the same way the app does."""

import httpx

from app.config import get_settings

OWNER = "baron@example.com"
HER = "her@example.com"


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


async def paired(make_client, outbox) -> tuple[httpx.AsyncClient, httpx.AsyncClient]:
    """Owner and partner, both signed in. Returns (his phone, her phone)."""
    me_phone, her_phone = make_client(), make_client()
    await sign_up_owner(me_phone, outbox)
    r = await sign_up_partner(her_phone, outbox, await make_invite(me_phone))
    assert r.status_code == 200, r.text
    return me_phone, her_phone


def error_code(r: httpx.Response) -> str:
    return r.json()["detail"]["code"]


def no_resend_cooldown(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "code_resend_seconds", 0)
