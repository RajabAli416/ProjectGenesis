"""Tolerant extraction of a JSON object from model text, followed by strict Pydantic validation."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


class ParseError(Exception):
    pass


def extract_json(text: str) -> dict:
    cleaned = _THINK_RE.sub("", text).strip()
    candidates = [cleaned]
    fence = _FENCE_RE.search(cleaned)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        candidates.append(cleaned[start : end + 1])
    last_err: Exception | None = None
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as e:
            last_err = e
    raise ParseError(f"no JSON object found: {last_err}")


def parse_as(text: str, model: type[T]) -> T:
    obj = extract_json(text)
    try:
        return model.model_validate(obj)
    except ValidationError as e:
        raise ParseError(_short(e)) from e


def _short(e: ValidationError) -> str:
    parts = []
    for err in e.errors()[:4]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)
