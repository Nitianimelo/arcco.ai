"""
Skill: Gerador de Apresentação de Slides (Design Source)

Retorna contrato estruturado (arcco.design-source/v1) para decks 16:9.
Não gera HTML.
"""

from __future__ import annotations

from backend.services.design_source_contract import (
    DesignFrame,
    DesignSourceDocument,
    canvas_from_preset,
    make_rect_element,
    make_text_element,
)
from backend.skills.design_source_skill_utils import (
    clamp_int,
    enumerate_chunks,
    extract_points,
    safe_title,
    serialize_doc,
)


SKILL_META = {
    "id": "slide_presentation_generator",
    "name": "Gerador de Apresentação de Slides",
    "description": (
        "Cria um design source para apresentação widescreen (16:9), pronto para render "
        "no Fabric.js e export backend em PNG/PDF/PPTX."
    ),
    "keywords": [
        "slide", "slides", "apresentação", "apresentacao", "deck", "pitch",
        "palestra", "powerpoint", "pptx", "carrossel",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Tema do deck."},
            "context_data": {"type": "string", "description": "Conteúdo ou pesquisa base."},
            "slide_count": {"type": "integer", "description": "Quantidade alvo de slides."},
        },
        "required": ["topic"],
    },
}


async def execute(args: dict) -> str:
    topic = safe_title(str(args.get("topic", "")), "Apresentação")
    context_data = str(args.get("context_data", "") or "")
    requested_slides = int(args.get("slide_count", 8) or 8)
    slide_count = clamp_int(requested_slides, 4, 20)

    canvas = canvas_from_preset("slide_widescreen")
    points = extract_points(context_data, max_points=80)
    chunks = enumerate_chunks(points, 4) if points else []

    frames: list[DesignFrame] = []
    frames.append(
        DesignFrame(
            id="slide-1",
            name="Capa",
            background="#0B1020",
            elements=[
                make_rect_element(
                    element_id="top-band",
                    x=0,
                    y=0,
                    width=canvas.width,
                    height=180,
                    fill="#111C36",
                ),
                make_text_element(
                    element_id="title",
                    text=topic,
                    x=120,
                    y=320,
                    width=canvas.width - 240,
                    height=300,
                    font_size=86,
                    font_weight="bold",
                    fill="#F8FAFC",
                    text_align="left",
                ),
                make_text_element(
                    element_id="subtitle",
                    text="Deck estruturado para apresentação executiva",
                    x=120,
                    y=680,
                    width=canvas.width - 240,
                    height=110,
                    font_size=42,
                    fill="#CBD5E1",
                    text_align="left",
                ),
            ],
        )
    )

    content_slides = slide_count - 1
    for i in range(content_slides):
        chunk = chunks[i] if i < len(chunks) else []
        if not chunk:
            chunk = ["Ponto em construção para esta etapa do deck."]
        body_text = "\n".join([f"• {line}" for line in chunk[:4]])
        slide_index = i + 2
        frames.append(
            DesignFrame(
                id=f"slide-{slide_index}",
                name=f"Slide {slide_index}",
                background="#FFFFFF",
                elements=[
                    make_rect_element(
                        element_id=f"accent-{slide_index}",
                        x=0,
                        y=0,
                        width=20,
                        height=canvas.height,
                        fill="#2563EB",
                    ),
                    make_text_element(
                        element_id=f"heading-{slide_index}",
                        text=f"Tópico {i + 1}",
                        x=110,
                        y=90,
                        width=canvas.width - 190,
                        height=110,
                        font_size=58,
                        font_weight="bold",
                        fill="#0F172A",
                        text_align="left",
                    ),
                    make_text_element(
                        element_id=f"bullets-{slide_index}",
                        text=body_text,
                        x=120,
                        y=260,
                        width=canvas.width - 240,
                        height=canvas.height - 360,
                        font_size=40,
                        fill="#1E293B",
                        text_align="left",
                    ),
                ],
            )
        )

    doc = DesignSourceDocument(
        kind="slide_presentation",
        title=topic,
        canvas=canvas,
        frames=frames,
        metadata={
            "render_engine": "fabric.js",
            "format_profile": "slide_16_9",
            "source": "slide_presentation_generator",
        },
    )
    return serialize_doc(doc)

