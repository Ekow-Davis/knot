"""Secrets, codes and signed tickets. Standard library only, so it's easy to test on its own.

Nothing secret is ever stored in readable form:
  • email codes and pairing codes → HMAC-SHA256 keyed with SECRET_KEY
  • session tokens               → SHA-256 (they're already 256 bits of randomness)
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

# No 0/O, 1/I/L: easy to read aloud or copy from a message.
INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVITE_LENGTH = 5  # TIE-XXXXX → 31^5 ≈ 28 million combinations, plus attempt limits.


def keyed_hash(secret: str, purpose: str, value: str) -> str:
    """HMAC-SHA256 hex. `purpose` keeps an email code from ever matching a pairing code."""
    return hmac.new(secret.encode(), f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def same(a: str, b: str) -> bool:
    """Constant-time comparison, so timing can't reveal how much of a code was right."""
    return hmac.compare_digest(a.encode(), b.encode())


# ── Email codes ───────────────────────────────────────────────────────────────


def new_email_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ── Pairing codes ─────────────────────────────────────────────────────────────


def new_invite_code() -> str:
    body = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))
    return f"TIE-{body}"


def normalize_invite(raw: str) -> str:
    """Accept 'tie-7k4mq', 'TIE 7K4MQ', '7k4mq' … and return 'TIE-7K4MQ'."""
    s = re.sub(r"[^A-Z0-9]", "", raw.upper())
    # Only strip the prefix when it's clearly there, so a body like "TIEAB" survives.
    if len(s) == INVITE_LENGTH + 3 and s.startswith("TIE"):
        s = s[3:]
    return f"TIE-{s}"


# ── Sessions ──────────────────────────────────────────────────────────────────


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Verified-email tickets ────────────────────────────────────────────────────
# After someone proves they own an email but has no account yet, they get a short-lived ticket.
# It's signed, not stored: the server can check it without a table.


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def make_ticket(secret: str, email: str, ttl_seconds: int, now: float | None = None) -> str:
    payload = {"e": email, "x": int((now or time.time()) + ttl_seconds), "n": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{body}.{keyed_hash(secret, 'ticket', body)}"


def read_ticket(secret: str, ticket: str, now: float | None = None) -> dict | None:
    """Returns {"e": email, "x": expiry, "n": nonce} or None if forged, malformed or expired."""
    try:
        body, sig = ticket.split(".", 1)
        if not same(sig, keyed_hash(secret, "ticket", body)):
            return None
        payload = json.loads(_unb64(body))
        if payload["x"] < (now or time.time()):
            return None
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        return None
