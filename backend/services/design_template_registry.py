from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "design_templates.json"


@lru_cache(maxsize=1)
def load_design_templates() -> list[dict[str, Any]]:
    with _DATA_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("design_templates.json deve conter uma lista.")
    return [item for item in data if isinstance(item, dict) and item.get("id")]


def list_design_templates(family: str | None = None) -> list[dict[str, Any]]:
    items = load_design_templates()
    if not family:
        return items
    normalized = family.strip().lower()
    return [item for item in items if str(item.get("family", "")).lower() == normalized]


def get_design_template(template_id: str) -> dict[str, Any] | None:
    normalized = (template_id or "").strip().lower()
    if not normalized:
        return None
    for item in load_design_templates():
        if str(item.get("id", "")).lower() == normalized:
            return item
    return None


def infer_template_family(topic: str, format_hint: str = "", context_data: str = "") -> str:
    haystack = f"{topic} {format_hint} {context_data}".lower()
    if any(token in haystack for token in ("story", "stories", "instagram story")):
        return "story"
    if any(token in haystack for token in ("a4", "folha corrida", "pdf", "impress", "impressão")):
        return "a4"
    if any(token in haystack for token in ("slide", "slides", "apresenta", "deck", "pitch", "ppt")):
        return "slide"
    return "feed"


def _match_format_hint(item: dict[str, Any], format_hint: str) -> int:
    hint = (format_hint or "").lower()
    item_format = str(item.get("format", "")).lower()
    preset = str(item.get("canvas_preset", "")).lower()
    if not hint:
        return 0
    score = 0
    if "1080x1350" in hint or "4:5" in hint or "vertical" in hint or "retrato" in hint:
        if "1350" in item_format or preset == "instagram-portrait":
            score += 6
    if "1080x1080" in hint or "1:1" in hint or "quadrado" in hint:
        if "1080x1080" in item_format or preset == "instagram-square":
            score += 6
    if "1080x1920" in hint or "9:16" in hint or "story" in hint:
        if "1920" in item_format or preset == "story":
            score += 6
    if "a4" in hint:
        if preset.startswith("a4"):
            score += 6
    if "16:9" in hint or "slide" in hint or "widescreen" in hint:
        if preset == "widescreen":
            score += 6
    return score


def pick_design_template(topic: str, family: str, context_data: str = "", format_hint: str = "") -> dict[str, Any] | None:
    haystack = f"{topic} {context_data}".lower()
    best_item: dict[str, Any] | None = None
    best_score = -1

    for item in list_design_templates(family):
        score = 0
        score += _match_format_hint(item, format_hint)
        for tag in item.get("tags", []):
            if str(tag).lower() in haystack:
                score += 3
        for token in (
            str(item.get("label", "")).lower(),
            str(item.get("category", "")).lower(),
            str(item.get("description", "")).lower(),
        ):
            if token and token in haystack:
                score += 1
        if score > best_score:
            best_item = item
            best_score = score

    if best_item:
        return best_item
    items = list_design_templates(family)
    return items[0] if items else None


def build_slot_defaults(topic: str, context_data: str, template: dict[str, Any] | None) -> dict[str, str]:
    slots = list((template or {}).get("slots", []))
    headline = topic.strip() or "Título principal"
    support = (context_data or "").strip().replace("\n", " ")
    support = support[:180] if support else "Mensagem principal da peça."
    defaults: dict[str, str] = {}
    for slot in slots:
        if slot in {"headline", "heading", "title"}:
            defaults[slot] = headline[:96]
        elif slot in {"subheadline", "subtitle", "intro", "summary", "support_body"}:
            defaults[slot] = support
        elif slot in {"cta", "closing"}:
            defaults[slot] = "Personalize a chamada final conforme a campanha."
        elif slot in {"eyebrow", "section_kicker", "badge"}:
            defaults[slot] = "Novo"
        elif slot in {"hero_image", "cover_image"}:
            defaults[slot] = ""
        elif slot == "big_value":
            defaults[slot] = "73%"
        elif slot == "signature":
            defaults[slot] = "Equipe Arcco"
        elif slot == "footer_note":
            defaults[slot] = "Ajuste os detalhes finais antes da apresentação."
        elif slot == "supporting_points":
            defaults[slot] = "Ponto 1 | Ponto 2 | Ponto 3"
        else:
            defaults[slot] = support
    return defaults
