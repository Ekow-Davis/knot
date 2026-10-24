"""Import a question pack into the database without ever printing a question.

    python -m app.tools.import_pack path/to/silly-002.pack      # encrypted (the real bank)
    python -m app.tools.import_pack sample/test-000.json        # plain JSON (throwaway test packs)
    python -m app.tools.import_pack --remove test-000           # take a pack (and its questions) out

Safe to run twice: a pack with the same checksum is skipped, and question ids that already
exist are left alone, so anything already played stays played.
Output is counts only (category × depth), never text.
"""

import argparse
import asyncio
import hashlib
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import delete, select

from ..bank import BankKeyMissing, bank_key, parse_pack, seal_question
from ..db import SessionLocal, engine
from ..models import DEPTHS, Question, QuestionPack


def _table(counts: Counter) -> str:
    cats = sorted({c for c, _ in counts})
    lines = [f"  {'category':<10}" + "".join(f"{d:>8}" for d in DEPTHS)]
    for c in cats:
        lines.append(f"  {c:<10}" + "".join(f"{counts.get((c, d), 0):>8}" for d in DEPTHS))
    return "\n".join(lines)


async def import_pack(path: Path) -> int:
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    try:
        key = bank_key()
        pack = parse_pack(raw)
    except BankKeyMissing as e:
        print(e, file=sys.stderr)
        return 2
    except Exception as e:  # wrong key, corrupt file, invalid questions
        # The validation error can quote question text, so only show its first line for encrypted packs.
        msg = str(e).splitlines()[0] if raw.startswith(b"KNOTPACK1") else str(e)
        print(f"Couldn't read that pack: {msg}", file=sys.stderr)
        return 1

    async with SessionLocal() as db:
        existing = await db.get(QuestionPack, pack.id)
        if existing and existing.checksum == checksum:
            print(f"{pack.id}: already imported, nothing to do.")
            return 0

        # The pack row must exist before any question points at it.
        if existing:
            existing.checksum, existing.version = checksum, pack.version
            existing.question_count = len(pack.questions)
        else:
            db.add(QuestionPack(id=pack.id, version=pack.version, checksum=checksum, question_count=len(pack.questions)))
        await db.flush()

        known = set(
            (await db.execute(select(Question.id).where(Question.id.in_([q.id for q in pack.questions])))).scalars()
        )
        added: Counter = Counter()
        for q in pack.questions:
            if q.id in known:
                continue
            ct, nonce = seal_question(key, q.id, q.payload())
            db.add(
                Question(
                    id=q.id,
                    pack_id=pack.id,
                    type=q.type,
                    depth=q.depth,
                    category=q.category,
                    payload=ct,
                    payload_nonce=nonce,
                )
            )
            added[(q.category, q.depth)] += 1

        await db.commit()

    total = sum(added.values())
    print(f"{pack.id} v{pack.version}: added {total} new question(s), {len(known)} already there.")
    if total:
        print(_table(added))
    return 0


async def remove_pack(pack_id: str) -> int:
    async with SessionLocal() as db:
        n = (await db.execute(delete(Question).where(Question.pack_id == pack_id))).rowcount
        await db.execute(delete(QuestionPack).where(QuestionPack.id == pack_id))
        await db.commit()
    print(f"Removed {pack_id} ({n} question(s)).")
    return 0


async def _main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="?", type=Path)
    p.add_argument("--remove", metavar="PACK_ID")
    args = p.parse_args(argv)
    try:
        if args.remove:
            return await remove_pack(args.remove)
        if not args.file:
            p.error("give a pack file, or --remove PACK_ID")
        return await import_pack(args.file)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
