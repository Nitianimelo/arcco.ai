"""
Skill: Gerador de Post Estático para Instagram (Design Source)
"""

from __future__ import annotations

from backend.services.design_source_contract import (
    DesignFrame,
    DesignSourceDocument,
    canvas_from_preset,
    make_rect_element,
    make_text_element,
)
from backend.skills.design_source_skill_utils import extract_points, safe_title, serialize_doc


SKILL_META = {
    "id": "instagram_post_generator",
    "name": "Gerador de Post Instagram",
    "description": (
        "Gera design source para post estático de Instagram (1080x1080). "
        "Retorna estrutura pronta para Fabric.js, não HTML."
    ),
    # Desativado: supersedido por instagram_carousel_creator e static_design_generator.
    "keywords": ["instagram_canvas_source_internal"],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Tema do post."},
            "context_data": {"type": "string", "description": "Copy e dados de apoio."},
            "cta": {"type": "string", "description": "Chamada de ação desejada."},
        },
        "required": ["topic"],
    },
}


async def execute(args: dict) -> str:
    topic = safe_title(str(args.get("topic", "")), "Post Instagram")
    context_data = str(args.get("context_data", "") or "")
    cta = str(args.get("cta", "") or "Saiba mais")
    points = extract_points(context_data, max_points=4)

    canvas = canvas_from_preset("instagram_post")
    subtitle = points[0] if points else "Mensagem principal em destaque para feed."

    frame = DesignFrame(
        id="post-1",
        name="Post",
        background="#F8FAFC",
        elements=[
            make_rect_element(
                element_id="frame-bg",
                x=48,
                y=48,
                width=canvas.width - 96,
                height=canvas.height - 96,
                fill="#FFFFFF",
                stroke="#CBD5E1",
                stroke_width=2,
                corner_radius=24,
            ),
            make_text_element(
                element_id="headline",
                text=topic,
                x=110,
                y=180,
                width=canvas.width - 220,
                height=260,
                font_size=76,
                font_weight="bold",
                fill="#0F172A",
                text_align="left",
            ),
            make_text_element(
                element_id="subtitle",
                text=subtitle,
                x=110,
                y=500,
                width=canvas.width - 220,
                height=220,
                font_size=42,
                fill="#334155",
                text_align="left",
            ),
            make_rect_element(
                element_id="cta-bg",
                x=110,
                y=820,
                width=420,
                height=110,
                fill="#2563EB",
                corner_radius=18,
            ),
            make_text_element(
                element_id="cta-text",
                text=cta[:40],
                x=130,
                y=848,
                width=380,
                height=60,
                font_size=36,
                font_weight="bold",
                fill="#FFFFFF",
                text_align="center",
            ),
        ],
    )

    doc = DesignSourceDocument(
        kind="instagram_post",
        title=topic,
        canvas=canvas,
        frames=[frame],
        metadata={
            "render_engine": "fabric.js",
            "format_profile": "instagram_post_square",
            "source": "instagram_post_generator",
        },
    )
    return serialize_doc(doc)

