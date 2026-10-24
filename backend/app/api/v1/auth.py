import asyncio

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Checked when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password("not-a-real-password")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)):
    user = await db.users.find_one({"email": body.email})
    hashed = user["password_hash"] if user else _DUMMY_HASH

    # bcrypt is CPU-heavy: run it off the event loop so other requests aren't blocked.
    password_ok = await asyncio.to_thread(verify_password, body.password, hashed)

    if user is None or not password_ok or not user.get("is_active", True):
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")

    settings = get_settings()
    token = create_access_token(str(user["_id"]), user["role"])
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_minutes * 60,
        user=UserOut(id=str(user["_id"]), email=user["email"], name=user["name"], role=user["role"]),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)