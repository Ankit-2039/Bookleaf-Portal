from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    # bcrypt only uses the first 72 bytes; the login schema caps input length.
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, role: str, expires_minutes: int | None = None) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    minutes = s.access_token_minutes if expires_minutes is None else expires_minutes
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError (incl. ExpiredSignatureError) on any problem."""
    s = get_settings()
    return jwt.decode(
        token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]}
    )