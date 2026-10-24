"""Generate the VAPID key pair for notifications (once, ever — keep them forever).

    python -m app.tools.vapid

Paste both lines into api/.env (and Railway's Variables). Changing them later means every
phone has to tap "Allow tugs" again.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    # Private key as base64url DER: the form pywebpush documents for vapid_private_key.
    private_der = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    # Public key as the raw uncompressed point: what the browser's pushManager.subscribe() expects.
    public_raw = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    print(f"VAPID_PUBLIC_KEY={b64url(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={b64url(private_der)}")


if __name__ == "__main__":
    main()
