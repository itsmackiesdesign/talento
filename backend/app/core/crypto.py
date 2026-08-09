"""AES-256-GCM encryption for bot tokens at rest.

Bot tokens are the single most sensitive value we store: with one, an attacker can
impersonate a customer's bot and read every candidate message. They are therefore never
written to the database in plaintext, and never returned by the API (only a masked hint).
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_BYTES = 12


def _key() -> bytes:
    """Derive a stable 32-byte key from the configured secret.

    Accepts either a base64-encoded 32-byte key (recommended, generate with
    ``base64.urlsafe_b64encode(os.urandom(32))``) or an arbitrary passphrase, which is
    stretched via SHA-256 so misconfiguration degrades to "weaker key" rather than a crash.
    """
    raw = settings.BOT_TOKEN_ENCRYPTION_KEY
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(raw.encode()).digest()


def encrypt(plaintext: str) -> str:
    """Return base64(nonce || ciphertext||tag)."""
    aesgcm = AESGCM(_key())
    nonce = os.urandom(_NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(token: str) -> str:
    blob = base64.urlsafe_b64decode(token.encode())
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return AESGCM(_key()).decrypt(nonce, ct, None).decode()


def mask_token(token: str) -> str:
    """`123456789:AAH...xyz` -> `123456789:AAH***xyz` for safe display in the panel."""
    if ":" not in token:
        return "***"
    bot_id, secret = token.split(":", 1)
    if len(secret) <= 6:
        return f"{bot_id}:***"
    return f"{bot_id}:{secret[:3]}***{secret[-3:]}"
