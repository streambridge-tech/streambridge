"""Password hashing for local accounts (team mode).

Argon2id via argon2-cffi. The rest of the app depends only on these helpers,
so the algorithm can change without touching models or routes.
"""
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerifyMismatchError

_ph = PasswordHasher()

MIN_PASSWORD_LEN = 10


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(stored_hash: str, raw: str) -> bool:
    try:
        return _ph.verify(stored_hash, raw)
    except (VerifyMismatchError, InvalidHashError, Argon2Error):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _ph.check_needs_rehash(stored_hash)
    except (InvalidHashError, Argon2Error):
        return True


def password_error(raw: str) -> str | None:
    """Return a reason string if the password is unacceptable, else None."""
    if not isinstance(raw, str) or not raw.strip():
        return "Password must not be empty"
    if len(raw) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters"
    return None
