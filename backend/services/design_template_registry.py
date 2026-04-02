from __future__ import annotations

import json
import re
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


def _score_template(item: dict[str, Any], topic: str, context_data: str = "", format_hint: str = "") -> int:
    haystack = f"{topic} {context_data}".lower()
    score = 0
    score += _match_format_hint(item, format_hint)
    score += _semantic_template_score(item, haystack)
    return score


def _semantic_template_score(item: dict[str, Any], haystack: str) -> int:
    score = 0
    generic_tags = {"story", "feed", "slide", "slides", "instagram", "post", "square", "portrait", "carrossel", "carousel"}
    for tag in item.get("tags", []):
        tag_text = str(tag).lower()
        if tag_text and tag_text not in generic_tags and tag_text in haystack:
            score += 3
    for token in (
        str(item.get("label", "")).lower(),
        str(item.get("category", "")).lower(),
        str(item.get("description", "")).lower(),
    ):
        if token and token in haystack:
            score += 1
    return score


def pick_design_template(topic: str, family: str, context_data: str = "", format_hint: str = "") -> dict[str, Any] | None:
    best_item: dict[str, Any] | None = None
    best_score = -1

    for item in list_design_templates(family):
        score = _score_template(item, topic, context_data, format_hint)
        if score > best_score:
            best_item = item
            best_score = score

    if best_item:
        return best_item
    items = list_design_templates(family)
    return items[0] if items else None


def choose_design_route(topic: str, family: str, context_data: str = "", format_hint: str = "") -> dict[str, Any]:
    haystack = f"{topic} {context_data} {format_hint}".lower()
    best_item: dict[str, Any] | None = None
    best_score = -1
    best_semantic_score = -1
    for item in list_design_templates(family):
        score = _score_template(item, topic, context_data, format_hint)
        semantic_score = _semantic_template_score(item, f"{topic} {context_data}".lower())
        if score > best_score:
            best_item = item
            best_score = score
            best_semantic_score = semantic_score

    explicit_open = any(
        token in haystack
        for token in (
            "do zero",
            "sem template",
            "livre",
            "autoral",
            "fora do padrão",
            "fora do padrao",
            "experimental",
            "original",
            "único",
            "unico",
            "surpreendente",
        )
    )

    if explicit_open or not best_item:
        return {"mode": "open", "template": None, "score": best_score, "semantic_score": best_semantic_score}

    if family in {"story", "feed"}:
        if best_score >= 6 and best_semantic_score >= 3:
            mode = "deterministic"
        elif best_score >= 6 and best_semantic_score >= 1:
            mode = "guided"
        else:
            mode = "open"
    elif family == "a4":
        if best_score >= 7 and best_semantic_score >= 3:
            mode = "deterministic"
        elif best_score >= 5:
            mode = "guided"
        else:
            mode = "open"
    else:
        if best_score >= 8 and best_semantic_score >= 4:
            mode = "deterministic"
        elif best_score >= 5:
            mode = "guided"
        else:
            mode = "open"

    return {
        "mode": mode,
        "template": best_item if mode != "open" else None,
        "score": best_score,
        "semantic_score": best_semantic_score,
    }


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _trim_sentence(value: str, limit: int) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    if not clipped:
        clipped = text[:limit].rstrip(",;:-")
    return clipped + "…"


def _extract_first_quoted_phrase(text: str) -> str:
    match = re.search(r"[\"'“”‘’]([^\"“”‘’']{4,80})[\"'“”‘’]", text or "")
    return _collapse_whitespace(match.group(1)) if match else ""


def _infer_eyebrow(topic: str, context_data: str) -> str:
    haystack = f"{topic} {context_data}".lower()
    if "natal" in haystack:
        return "Especial de Natal"
    if "dia dos pais" in haystack:
        return "Dia dos Pais"
    if "páscoa" in haystack or "pascoa" in haystack:
        return "Especial de Páscoa"
    if any(token in haystack for token in ("promo", "oferta", "desconto", "sale")):
        return "Oferta"
    if "novo" in haystack or "lançamento" in haystack or "lancamento" in haystack:
        return "Novo"
    return "Destaque"


def _infer_headline(topic: str, context_data: str) -> str:
    lowered = f"{topic} {context_data}".lower()
    if "natal" in lowered and any(token in lowered for token in ("promo", "promoção", "promocao", "oferta", "desconto")):
        return "Ofertas de Natal"
    if "dia dos pais" in lowered and any(token in lowered for token in ("festa", "evento", "convite")):
        return "Festa de Dia dos Pais"
    quoted = _extract_first_quoted_phrase(context_data)
    if quoted and len(quoted) <= 48:
        return quoted
    normalized_topic = _collapse_whitespace(topic)
    cleaned = re.sub(
        r"^(post|story|banner|slide|apresenta[çc][ãa]o|carrossel)\s+(de|para)\s+",
        "",
        normalized_topic,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(post|story|banner|slide)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -:")
    return _trim_sentence(cleaned or normalized_topic or "Título principal", 56)


def _infer_subheadline(topic: str, context_data: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", context_data or "")
    cleaned_sentences = [
        _collapse_whitespace(sentence).strip(" -:")
        for sentence in sentences
        if _collapse_whitespace(sentence)
    ]
    if cleaned_sentences:
        candidate = cleaned_sentences[0]
        if len(candidate) < 40 and len(cleaned_sentences) > 1:
            candidate = f"{candidate} {cleaned_sentences[1]}"
        return _trim_sentence(candidate, 120)
    return _trim_sentence(topic or "Mensagem principal da peça.", 120)


def _infer_cta(topic: str, context_data: str) -> str:
    haystack = f"{topic} {context_data}"
    quoted_phrases = re.findall(r"[\"'“”‘’]([^\"“”‘’']{4,80})[\"'“”‘’]", haystack)
    for phrase in quoted_phrases:
        cleaned = _collapse_whitespace(phrase)
        if any(token in cleaned.lower() for token in ("aproveite", "confira", "ver", "garanta", "compre", "saiba", "celebre", "participe")):
            return _trim_sentence(cleaned, 38)
    lowered = haystack.lower()
    if "natal" in lowered and any(token in lowered for token in ("promo", "oferta", "desconto")):
        return "Ver ofertas"
    if "dia dos pais" in lowered:
        return "Celebrar agora"
    if any(token in lowered for token in ("evento", "festa", "convite", "inscrição", "inscricao")):
        return "Confirmar presença"
    if any(token in lowered for token in ("promo", "oferta", "desconto")):
        return "Aproveitar agora"
    return "Saiba mais"


def build_slot_defaults(topic: str, context_data: str, template: dict[str, Any] | None) -> dict[str, str]:
    slots = list((template or {}).get("slots", []))
    headline = _infer_headline(topic, context_data)
    support = _infer_subheadline(topic, context_data)
    eyebrow = _infer_eyebrow(topic, context_data)
    cta = _infer_cta(topic, context_data)
    defaults: dict[str, str] = {}
    for slot in slots:
        if slot in {"headline", "heading", "title"}:
            defaults[slot] = headline[:96]
        elif slot in {"subheadline", "subtitle", "intro", "summary", "support_body"}:
            defaults[slot] = support
        elif slot in {"cta", "closing"}:
            defaults[slot] = cta
        elif slot in {"eyebrow", "section_kicker", "badge"}:
            defaults[slot] = eyebrow
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
        elif slot == "logo":
            defaults[slot] = ""
        else:
            defaults[slot] = support
    return defaults
