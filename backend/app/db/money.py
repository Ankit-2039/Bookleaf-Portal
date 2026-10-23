from decimal import Decimal

from bson.decimal128 import Decimal128


def to_d128(value) -> Decimal128 | None:
    """Python number/str -> exact Mongo Decimal128. None stays None (e.g. MRP of unpublished books)."""
    if value is None:
        return None
    return Decimal128(Decimal(str(value)))


def from_d128(value) -> Decimal | None:
    """Mongo value -> Decimal for safe arithmetic and JSON serialization."""
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))