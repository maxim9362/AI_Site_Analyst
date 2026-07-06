"""Encode/decode OAuth tokens for secure storage.

If TOKEN_ENCRYPTION_KEY is set, tokens are encrypted with Fernet.
If not set in local/dev, tokens are stored as plaintext with a warning.
In production without a key, encoding raises an error.
"""
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_PREFIX = "enc:"


def _get_fernet():
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode() if isinstance(key, str) else key)


def is_token_encryption_enabled() -> bool:
    return bool(settings.TOKEN_ENCRYPTION_KEY)


def encode_token(token: str | None) -> str | None:
    """Encode a token for storage. Returns encrypted value with 'enc:' prefix."""
    if token is None:
        return None

    # Already encrypted — do not double-encrypt.
    if token.startswith(_TOKEN_PREFIX):
        return token

    fernet = _get_fernet()
    if fernet is None:
        if settings.APP_ENV == "production":
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY is required in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        logger.warning(
            "TOKEN_ENCRYPTION_KEY is not set. OAuth tokens are stored in plaintext in %s mode.",
            settings.APP_ENV,
        )
        return token

    encrypted = fernet.encrypt(token.encode()).decode()
    return f"{_TOKEN_PREFIX}{encrypted}"


def decode_token(token: str | None) -> str | None:
    """Decode a stored token. Handles both encrypted and plaintext formats."""
    if token is None:
        return None

    if token.startswith(_TOKEN_PREFIX):
        fernet = _get_fernet()
        if fernet is None:
            logger.error("Token has 'enc:' prefix but TOKEN_ENCRYPTION_KEY is not set.")
            return None
        raw = token[len(_TOKEN_PREFIX):]
        return fernet.decrypt(raw.encode()).decode()

    # Plaintext token (local/dev only).
    if settings.APP_ENV == "production":
        logger.error("Plaintext token found in production. TOKEN_ENCRYPTION_KEY may have been added after tokens were saved.")
        return None

    return token
