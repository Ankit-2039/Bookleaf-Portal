import bcrypt


def hash_password(plain: str) -> str:
    # bcrypt only uses the first 72 bytes; we cap input length at the API layer later.
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False