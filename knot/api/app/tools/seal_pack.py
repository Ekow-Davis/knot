"""Encrypt a plain JSON pack into a .pack file (used when the bank is generated).

    python -m app.tools.seal_pack silly-002.json silly-002.pack

Run it, then delete the .json. The .pack is the only thing that should ever travel.
"""

import sys
from pathlib import Path

from ..bank import BankKeyMissing, PackFile, bank_key, seal_pack


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    raw = src.read_bytes()
    PackFile.model_validate_json(raw)  # refuse to seal something that won't import
    try:
        dst.write_bytes(seal_pack(bank_key(), raw))
    except BankKeyMissing as e:
        print(e, file=sys.stderr)
        return 2
    print(f"Sealed {src.name} → {dst.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
