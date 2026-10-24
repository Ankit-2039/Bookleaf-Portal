from bson import ObjectId
from bson.errors import InvalidId

from app.core.errors import AppError


def parse_object_id(value: str, what: str = "Resource") -> ObjectId:
    """Malformed ids get the same 404 as missing ones."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise AppError(404, "not_found", f"{what} not found.")