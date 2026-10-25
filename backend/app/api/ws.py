import asyncio
import logging
import time

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db import mongo
from app.models.enums import UserRole
from app.realtime.events import ADMINS_CHANNEL, author_channel
from app.realtime.manager import hub

logger = logging.getLogger("bookleaf.realtime")
router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT = 5.0  # seconds allowed between connecting and sending the auth message
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403


async def _authenticate(db, token: str) -> tuple[dict, float]:
    payload = decode_access_token(token)  # raises jwt.InvalidTokenError
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if user is None or not user.get("is_active", True):
        raise ValueError("unknown or inactive user")
    return user, float(payload["exp"])


@router.websocket("/ws")
async def realtime(websocket: WebSocket) -> None:
    """ws(s)://<host>/api/v1/ws. First message must be {"type":"auth","token":"<JWT>"}.
    Server then sends {"type":"ready"} followed by ticket events. Client may send {"type":"ping"}."""
    # CORS does not protect WebSockets, so check the Origin header explicitly.
    origin = websocket.headers.get("origin")
    if origin and origin not in get_settings().cors_origin_list:
        await websocket.close(code=CLOSE_FORBIDDEN)  # before accept: handshake refused
        return
    await websocket.accept()

    db = mongo.get_db()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT)
        if not (isinstance(first, dict) and first.get("type") == "auth" and isinstance(first.get("token"), str)):
            raise ValueError("expected an auth message")
        user, exp = await _authenticate(db, first["token"])
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError, TypeError, KeyError, InvalidId, jwt.InvalidTokenError):
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    role = UserRole(user["role"])
    if role == UserRole.ADMIN:
        channel = ADMINS_CHANNEL
    else:
        author = await db.authors.find_one({"user_id": user["_id"]}, {"_id": 1})
        if author is None:
            await websocket.close(code=CLOSE_FORBIDDEN)
            return
        channel = author_channel(author["_id"])  # derived from the token, never from client input

    hub.add(channel, websocket)
    try:
        await websocket.send_json({"type": "ready", "role": role.value})
        while True:
            remaining = exp - time.time()
            if remaining <= 0:
                break
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            except ValueError:
                continue  # ignore frames that are not JSON
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
        # The session's token has expired: end the connection, the client must log in again.
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="token_expired")
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(channel, websocket)