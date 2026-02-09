"""Password hashing utilities using bcrypt."""

import bcrypt

# bcrypt has a 72-byte limit; we truncate to avoid errors with newer bcrypt
BCRYPT_MAX_PASSWORD_BYTES = 72


def _to_bytes(password: str) -> bytes:
    """Encode password to bytes, truncating to bcrypt's 72-byte limit."""
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_PASSWORD_BYTES:
        return raw[:BCRYPT_MAX_PASSWORD_BYTES]
    return raw


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string (decoded for storage).
    """
    pw_bytes = _to_bytes(password)
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to check against

    Returns:
        True if password matches, False otherwise
    """
    pw_bytes = _to_bytes(plain_password)
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False
