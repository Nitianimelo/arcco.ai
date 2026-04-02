from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.design_template_registry import (
    build_slot_defaults,
    get_design_template,
)
from backend.services.unsplash import build_unsplash_url


_TEMPLATES_DIR = Path(__file__).parent / "design_templates"


def _image_size_from_preset(canvas_preset: str | None) -> tuple[int, int]:
    if canvas_preset == "story":
        return 1080, 1920
    if canvas_preset == "instagram-portrait":
        return 1080, 1350
    if canvas_preset == "widescreen":
        return 1280, 720
    return 1080, 1080


def _load_template(template_file: str) -> str:
    return (_TEMPLATES_DIR / template_file).read_text(encoding="utf-8")


def _merge_slots(payload: dict[str, Any], template: dict[str, Any]) -> dict[str, str]:
    slots = build_slot_defaults(payload.get("title", ""), payload.get("context_data", ""), template)
    slots.update({k: str(v) for k, v in (payload.get("slot_updates") or {}).items() if v is not None})
    return slots


def _resolve_image_url(payload: dict[str, Any], template: dict[str, Any]) -> str | None:
    image_url = payload.get("image_url")
    if image_url:
        return str(image_url)
    if not template.get("requires_image"):
        return None
    query = payload.get("image_query") or template.get("default_image_query") or payload.get("title") or "premium editorial"
    width, height = _image_size_from_preset(payload.get("canvas_preset") or template.get("canvas_preset"))
    return build_unsplash_url(str(query), width=width, height=height)


def _replace_tokens(template_html: str, mapping: dict[str, str]) -> str:
    rendered = template_html
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def _render_single_canvas(payload: dict[str, Any], template: dict[str, Any]) -> str:
    slots = _merge_slots(payload, template)
    hero_image_url = _resolve_image_url(payload, template) or ""
    html = _load_template(str(template["template_file"]))
    mapping = {"title": str(payload.get("title") or template.get("label") or "Design"), "hero_image_url": hero_image_url}
    for key, value in slots.items():
        mapping[f"slots.{key}"] = value
    return _replace_tokens(html, mapping)


def _render_slide_block(template_html: str, slide: dict[str, Any], deck_label: str, fallback_big_value: str) -> str:
    points = slide.get("points") or []
    if points:
        points_html = "<ul>" + "".join(f"<li>{point}</li>" for point in points) + "</ul>"
    else:
        points_html = f"<p>{slide.get('support', '')}</p>"
    hero_image_html = (
        f'<img src="{slide["hero_image_url"]}" alt="{slide.get("heading", deck_label)}" />'
        if slide.get("hero_image_url")
        else f'<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2cqw;color:#94a3b8;">{deck_label}</div>'
    )
    mapping = {
        "title": slide.get("heading", deck_label),
        "slide.kicker": slide.get("kicker", deck_label),
        "slide.heading": slide.get("heading", deck_label),
        "slide.points_html": points_html,
        "slide.big_value": slide.get("big_value") or fallback_big_value,
        "slide.support": slide.get("support", ""),
        "slide.note": slide.get("note", ""),
        "slide.hero_image_html": hero_image_html,
    }
    return _replace_tokens(template_html, mapping)


def _render_slide_deck(payload: dict[str, Any], template: dict[str, Any]) -> str:
    template_html = _load_template(str(template["template_file"]))
    deck_slots = _merge_slots(payload, template)
    hero_image_url = _resolve_image_url(payload, template)
    rendered_slides: list[str] = []
    for index, slide in enumerate(payload.get("slides") or [], start=1):
        points = slide.get("points") or []
        rendered_slides.append(
            _render_slide_block(
                template_html,
                {
                    "kicker": deck_slots.get("section_kicker", f"Slide {index:02d}"),
                    "heading": slide.get("heading") or deck_slots.get("heading") or payload.get("title") or "Slide",
                    "points": points,
                    "big_value": slide.get("big_value") or deck_slots.get("big_value"),
                    "support": " ".join(points[:3]) if points else deck_slots.get("supporting_points", ""),
                    "note": slide.get("speaker_notes") or deck_slots.get("speaker_note") or "",
                    "hero_image_url": hero_image_url,
                },
                template.get("label", "Slide"),
                deck_slots.get("big_value", "73%"),
            )
        )
    if not rendered_slides:
        rendered_slides.append(
            _render_slide_block(
                template_html,
                {
                    "kicker": deck_slots.get("section_kicker", "Slide 01"),
                    "heading": payload.get("title") or deck_slots.get("heading") or "Apresentação",
                    "points": [],
                    "big_value": deck_slots.get("big_value"),
                    "support": deck_slots.get("supporting_points", ""),
                    "note": deck_slots.get("speaker_note", ""),
                    "hero_image_url": hero_image_url,
                },
                template.get("label", "Slide"),
                deck_slots.get("big_value", "73%"),
            )
        )
    return "<!-- ARCCO_DESIGN_SEPARATOR -->".join(rendered_slides)


def render_design_template_from_payload(payload: dict[str, Any]) -> str | None:
    template_id = str(payload.get("template_id") or "").strip()
    if not template_id:
        return None
    template = get_design_template(template_id)
    if not template or not template.get("template_file"):
        return None
    family = str(payload.get("template_family") or template.get("family") or "").lower()
    if family == "slide":
        return _render_slide_deck(payload, template)
    return _render_single_canvas(payload, template)


def parse_template_payload(raw: str) -> dict[str, Any] | None:
    import json

    try:
        data = json.loads((raw or "").strip())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("template_id"):
        return None
    return data


def render_design_template_from_context(raw: str) -> str | None:
    payload = parse_template_payload(raw)
    if not payload:
        return None
    return render_design_template_from_payload(payload)
