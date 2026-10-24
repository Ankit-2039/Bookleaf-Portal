from dataclasses import dataclass

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.mongo import get_db
from app.models.enums import UserRole

bearer_scheme = HTTPBearer(auto_error=False)  # we raise our own consistent errors


@dataclass(frozen=True)
class CurrentUser:
    oid: ObjectId
    email: str
    name: str
    role: UserRole

    @property
    def id(self) -> str:
        return str(self.oid)


def _unauthenticated(message: str = "Authentication required.") -> AppError:
    return AppError(401, "not_authenticated", message, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db=Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise _unauthenticated()
    try:
        payload = decode_access_token(creds.credentials)
        oid = ObjectId(payload["sub"])
    except (jwt.InvalidTokenError, InvalidId, KeyError):
        raise _unauthenticated("Invalid or expired token.")

    # Source of truth is the database: role and active flag are re-checked every request.
    user = await db.users.find_one({"_id": oid})
    if user is None or not user.get("is_active", True):
        raise _unauthenticated("Invalid or expired token.")

    return CurrentUser(oid=user["_id"], email=user["email"], name=user["name"], role=UserRole(user["role"]))


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.ADMIN:
        raise AppError(403, "forbidden", "Admin access required.")
    return user


async def require_author(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.AUTHOR:
        raise AppError(403, "forbidden", "Author access required.")
    return user

async def get_author_profile(
    user: CurrentUser = Depends(require_author), db=Depends(get_db)
) -> dict:
    """The authenticated author's profile document. All author data is scoped by its _id."""
    author = await db.authors.find_one({"user_id": user.oid})
    if author is None:
        raise AppError(403, "no_author_profile", "No author profile is linked to this account.")
    return author