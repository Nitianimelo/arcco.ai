from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "story_templates.json"


@lru_cache(maxsize=1)
def load_story_templates() -> list[dict[str, Any]]:
    with _DATA_PATH.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, list):
        raise ValueError("story_templates.json deve conter uma lista.")
    return [item for item in raw if isinstance(item, dict) and item.get("id")]


def list_story_templates() -> list[dict[str, Any]]:
    return load_story_templates()


def get_story_template(template_id: str) -> dict[str, Any] | None:
    normalized = (template_id or "").strip().lower()
    if not normalized:
        return None
    for item in load_story_templates():
        if str(item.get("id", "")).lower() == normalized:
            return item
    return None


def pick_story_template(topic: str, context_data: str = "") -> dict[str, Any] | None:
    haystack = f"{topic} {context_data}".lower()
    best_item: dict[str, Any] | None = None
    best_score = -1

    for item in load_story_templates():
        score = 0
        for tag in item.get("tags", []):
            if tag.lower() in haystack:
                score += 3
        label = str(item.get("label", "")).lower()
        category = str(item.get("category", "")).lower()
        description = str(item.get("description", "")).lower()
        for token in (label, category, description):
            if token and token in haystack:
                score += 1
        if score > best_score:
            best_score = score
            best_item = item

    if best_item:
        return best_item
    templates = load_story_templates()
    return templates[0] if templates else None
