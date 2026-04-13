from __future__ import annotations

import json
import html
from pathlib import Path
import re
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


def _build_chart_html(chart_type: str, chart_title: str, labels: list[Any], values: list[Any], chart_id: str) -> str:
    normalized_labels = [str(item).strip()[:42] for item in labels if str(item).strip()]
    normalized_values: list[float] = []
    for value in values:
        try:
            normalized_values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not normalized_labels or not normalized_values or len(normalized_labels) != len(normalized_values):
        return ""
    palette = ["#60a5fa", "#38bdf8", "#818cf8", "#22c55e", "#f59e0b", "#f43f5e"]
    colors = [palette[index % len(palette)] for index in range(len(normalized_values))]
    config = {
        "type": chart_type,
        "data": {
            "labels": normalized_labels,
            "datasets": [
                {
                    "label": chart_title or "Indicador",
                    "data": normalized_values,
                    "backgroundColor": colors if chart_type != "line" else "rgba(96,165,250,0.18)",
                    "borderColor": colors if chart_type != "line" else "#60a5fa",
                    "borderWidth": 2,
                    "fill": chart_type == "line",
                    "tension": 0.32,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {"display": chart_type == "doughnut"},
                "title": {"display": bool(chart_title), "text": chart_title or ""},
            },
            "scales": {
                "y": {"beginAtZero": True},
            } if chart_type in {"bar", "line"} else {},
        },
    }
    safe_title = html.escape(chart_title or "Visualização de Dados")
    safe_config = json.dumps(config, ensure_ascii=False).replace("</script>", "<\\/script>")
    return (
        f'<div class="chart-shell">'
        f'<div class="chart-title">{safe_title}</div>'
        f'<div class="chart-stage"><canvas id="{chart_id}"></canvas></div>'
        f'<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'
        f'<script>'
        f'(function(){{'
        f'var el=document.getElementById("{chart_id}");'
        f'if(!el||typeof Chart==="undefined") return;'
        f'new Chart(el.getContext("2d"), {safe_config});'
        f'}})();'
        f'</script>'
        f'</div>'
    )


def _build_visual_html(slide: dict[str, Any], deck_label: str, fallback_big_value: str, chart_id: str) -> str:
    chart_type = str(slide.get("chart_type") or "").strip().lower()
    chart_labels = slide.get("chart_labels") or []
    chart_values = slide.get("chart_values") or []
    if chart_type in {"bar", "line", "doughnut"} and chart_labels and chart_values:
        chart_html = _build_chart_html(
            chart_type,
            str(slide.get("chart_title") or slide.get("heading") or deck_label),
            chart_labels,
            chart_values,
            chart_id,
        )
        if chart_html:
            return chart_html

    if slide.get("hero_image_url"):
        return f'<img src="{slide["hero_image_url"]}" alt="{html.escape(str(slide.get("heading", deck_label)))}" />'

    return f'<div class="metric-fallback">{html.escape(str(slide.get("big_value") or fallback_big_value or deck_label))}</div>'


def _render_single_canvas(payload: dict[str, Any], template: dict[str, Any]) -> str:
    slots = _merge_slots(payload, template)
    hero_image_url = _resolve_image_url(payload, template) or ""
    html = _load_template(str(template["template_file"]))
    mapping = {"title": str(payload.get("title") or template.get("label") or "Design"), "hero_image_url": hero_image_url}
    for key, value in slots.items():
        mapping[f"slots.{key}"] = value
    return _replace_tokens(html, mapping)


def _render_slide_block(template_html: str, slide: dict[str, Any], deck_label: str, fallback_big_value: str, chart_id: str) -> str:
    points = slide.get("points") or []
    if points:
        points_html = "<ul>" + "".join(f"<li>{point}</li>" for point in points) + "</ul>"
    else:
        points_html = f"<p>{slide.get('support', '')}</p>"
    visual_html = _build_visual_html(slide, deck_label, fallback_big_value, chart_id)
    mapping = {
        "title": slide.get("heading", deck_label),
        "slide.kicker": slide.get("kicker", deck_label),
        "slide.heading": slide.get("heading", deck_label),
        "slide.points_html": points_html,
        "slide.big_value": slide.get("big_value") or fallback_big_value,
        "slide.support": slide.get("support", ""),
        "slide.note": slide.get("note", ""),
        "slide.visual_html": visual_html,
        "slide.chart_title": slide.get("chart_title", ""),
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
                    "chart_type": slide.get("chart_type"),
                    "chart_title": slide.get("chart_title"),
                    "chart_labels": slide.get("chart_labels") or [],
                    "chart_values": slide.get("chart_values") or [],
                },
                template.get("label", "Slide"),
                deck_slots.get("big_value", "73%"),
                f"arcco-chart-{index}",
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
                    "chart_type": None,
                    "chart_title": "",
                    "chart_labels": [],
                    "chart_values": [],
                },
                template.get("label", "Slide"),
                deck_slots.get("big_value", "73%"),
                "arcco-chart-1",
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

    text = (raw or "").strip()
    try:
        data = json.loads(text)
    except Exception:
        match = None
        for candidate in (
            r'(\{[\s\S]*"template_id"[\s\S]*\})',
            r'(\{[\s\S]*"canvas_preset"[\s\S]*\})',
        ):
            match = re.search(candidate, text)
            if match:
                break
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
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
