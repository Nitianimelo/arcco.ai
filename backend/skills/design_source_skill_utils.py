from __future__ import annotations

import json
import re
from typing import Iterable

from backend.services.design_source_contract import DesignSourceDocument


def clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def extract_points(text: str, max_points: int = 32) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", text or "")
    points: list[str] = []
    for part in raw_parts:
        cleaned = clean_line(part).strip(" -•*")
        if len(cleaned) < 12:
            continue
        if cleaned in points:
            continue
        points.append(cleaned[:180])
        if len(points) >= max_points:
            break
    return points


def safe_title(value: str, fallback: str) -> str:
    candidate = clean_line(value)
    return candidate[:120] if candidate else fallback


def clamp_int(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def enumerate_chunks(items: Iterable[str], chunk_size: int) -> list[list[str]]:
    bucket: list[list[str]] = []
    current: list[str] = []
    for item in items:
        current.append(item)
        if len(current) >= chunk_size:
            bucket.append(current)
            current = []
    if current:
        bucket.append(current)
    return bucket


def serialize_doc(doc: DesignSourceDocument) -> str:
    return json.dumps(doc.model_dump(), ensure_ascii=False)

