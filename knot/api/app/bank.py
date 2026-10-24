"""The question bank's encryption. Baron never sees the questions, so:

  • A pack travels as an encrypted file:  b"KNOTPACK1" + 12-byte nonce + AES-GCM(JSON)
  • In the database, each question's text is its own AES-GCM blob (the question id is bound in
    as associated data, so blobs can't be swapped between questions). Only type, depth and
    category are readable, so the server can filter without decrypting.
  • A single question is decrypted only at the moment it's drawn.

The key is BANK_KEY (base64, 32 bytes), kept in Railway's variables — never in the repo.
"""

import base64
import json
import os
import re
from typing import Literal

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, field_validator, model_validator

from .config import get_settings
from .models import CATEGORIES

MAGIC = b"KNOTPACK1"


class BankKeyMissing(RuntimeError):
    pass


def bank_key() -> bytes:
    raw = get_settings().bank_key
    try:
        key = base64.b64decode(raw, validate=True) if raw else b""
    except ValueError:
        key = b""
    if len(key) != 32:
        raise BankKeyMissing(
            "BANK_KEY must be set to a base64 32-byte key. Generate one with:\n"
            '  python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"'
        )
    return key


# ── Single questions (database) ───────────────────────────────────────────────


def seal_question(key: bytes, question_id: str, payload: dict) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    return AESGCM(key).encrypt(nonce, data, question_id.encode()), nonce


def open_question(key: bytes, question_id: str, ciphertext: bytes, nonce: bytes) -> dict:
    return json.loads(AESGCM(key).decrypt(nonce, ciphertext, question_id.encode()))


# ── Whole packs (files) ───────────────────────────────────────────────────────


def seal_pack(key: bytes, plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, plaintext, MAGIC)


def open_pack(key: bytes, blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        raise ValueError("Not an encrypted Knot pack")
    nonce, ct = blob[len(MAGIC) : len(MAGIC) + 12], blob[len(MAGIC) + 12 :]
    return AESGCM(key).decrypt(nonce, ct, MAGIC)


# ── Pack format ───────────────────────────────────────────────────────────────


class PackQuestion(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    type: Literal["guess", "both", "wyr", "self"]
    depth: Literal["light", "medium", "deep"]
    category: str
    q: str = Field(min_length=3, max_length=300)
    options: list[str] | None = None

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown category {v!r}")
        return v

    @model_validator(mode="after")
    def _shape(self):
        if self.type == "wyr":
            if not self.options or len(self.options) != 2 or not all(1 <= len(o) <= 120 for o in self.options):
                raise ValueError(f"{self.id}: Would-you-rather needs exactly two options")
        elif self.options:
            raise ValueError(f"{self.id}: only Would-you-rather questions have options")
        # Guess questions are about the other person, named with {p}.
        if self.type == "guess" and "{p}" not in self.q:
            raise ValueError(f"{self.id}: Guess questions must name the person with {{p}}")
        if re.search(r"\{(?!p\})", self.q):
            raise ValueError(f"{self.id}: the only placeholder allowed is {{p}}")
        return self

    def payload(self) -> dict:
        out: dict = {"q": self.q}
        if self.options:
            out["options"] = self.options
        return out


class PackFile(BaseModel):
    id: str = Field(pattern=r"^[a-z]+-\d{3}$")  # e.g. "silly-002", "test-000"
    version: int = Field(ge=1, default=1)
    questions: list[PackQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self):
        ids = [q.id for q in self.questions]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate question ids: {sorted(dupes)}")
        return self


def parse_pack(raw: bytes, pack_key: bytes | None = None) -> PackFile:
    """Plain JSON (test packs) or an encrypted .pack file (the real bank).
    Packs travel sealed with a transport key (pack_key); without one, BANK_KEY is tried."""
    data = open_pack(pack_key or bank_key(), raw) if raw.startswith(MAGIC) else raw
    return PackFile.model_validate_json(data)


def read_key_file(path) -> bytes:
    """A transport key file: one line of base64 (32 bytes)."""
    from pathlib import Path

    key = base64.b64decode(Path(path).read_text().strip(), validate=True)
    if len(key) != 32:
        raise ValueError("a pack key must be 32 bytes")
    return key
