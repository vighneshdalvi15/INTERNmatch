from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId


def parse_oid(value: str | None) -> ObjectId | None:
    """Return ObjectId or None for invalid / missing ids (avoids 500s on bad input)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > 24:
        return None
    try:
        return ObjectId(s)
    except (InvalidId, TypeError, ValueError):
        return None


def oid(value: str) -> ObjectId:
    """Strict ObjectId parse; raises InvalidId when value is invalid."""
    parsed = parse_oid(value)
    if parsed is None:
        raise InvalidId(value)
    return parsed


def str_oid(value: ObjectId) -> str:
    return str(value)


def _serialize_value(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, list):
        return [_serialize_value(x) for x in v]
    if isinstance(v, dict):
        return serialize_doc(v)
    return v


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        else:
            out[k] = _serialize_value(v)
    return out
