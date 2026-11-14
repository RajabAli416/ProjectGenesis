from __future__ import annotations

import hashlib
import re
from typing import Any

import orjson


def canonical_json(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS | orjson.OPT_SERIALIZE_NUMPY)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_obj(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


# Local ids look like "a-01-0001" / "m-01-0149" / "ev-01-000056": prefix, universe number, sequence.
_LOCAL_ID_RE = re.compile(rb"\b([A-Za-z]{1,4})-\d{2}-(\d{4,6})\b")
_LOCAL_ID_STR_RE = re.compile(r"\b([A-Za-z]{1,4})-\d{2}-(\d{4,6})\b")


def neutralise_ids(data: bytes) -> bytes:
    """Replace the universe-number segment of local ids so content from different universe
    instances (same seed, different number) hashes identically."""
    return _LOCAL_ID_RE.sub(rb"\1-XX-\2", data)


def neutralise_ids_str(text: str) -> str:
    return _LOCAL_ID_STR_RE.sub(r"\1-XX-\2", text)
