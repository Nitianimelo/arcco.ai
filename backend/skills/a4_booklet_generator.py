"""
Skill: Gerador de Apostila A4 (Design Source)

Retorna contrato estruturado (arcco.design-source/v1) para apostila A4.
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
    "id": "a4_booklet_generator",
    "name": "Gerador de Apostila A4",
    "description": (
        "Cria a estrutura de design source para apostilas A4 em 300 DPI. "
        "Retorna páginas com elementos posicionados para renderização via Fabric.js."
    ),
    "keywords": [
        "apostila", "a4", "manual", "material didático", "material didatico",
        "booklet", "documento a4", "diagramação a4", "diagramacao a4",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Tema central da apostila."},
            "context_data": {"type": "string", "description": "Conteúdo base da apostila."},
            "page_count": {"type": "integer", "description": "Número alvo de páginas."},
        },
        "required": ["topic"],
    },
}


async def execute(args: dict) -> str:
    topic = safe_title(str(args.get("topic", "")), "Apostila Técnica")
    context_data = str(args.get("context_data", "") or "")
    requested_pages = int(args.get("page_count", 6) or 6)
    page_count = clamp_int(requested_pages, 4, 24)

    canvas = canvas_from_preset("a4_booklet")
    points = extract_points(context_data, max_points=120)
    chunks = enumerate_chunks(points, 6) if points else []

    frames: list[DesignFrame] = []

    cover = DesignFrame(
        id="page-1",
        name="Capa",
        background="#0B1220",
        elements=[
            make_rect_element(
                element_id="cover-strip",
                x=0,
                y=0,
                width=canvas.width,
                height=420,
                fill="#111B33",
            ),
            make_text_element(
                element_id="cover-title",
                text=topic,
                x=180,
                y=560,
                width=canvas.width - 360,
                height=440,
                font_size=110,
                font_weight="bold",
                fill="#F8FAFC",
                text_align="left",
            ),
            make_text_element(
                element_id="cover-subtitle",
                text="Edição profissional em formato A4",
                x=180,
                y=1100,
                width=canvas.width - 360,
                height=120,
                font_size=48,
                font_weight="normal",
                fill="#CBD5E1",
                text_align="left",
            ),
        ],
    )
    frames.append(cover)

    for idx in range(2, page_count + 1):
        chunk = chunks[idx - 2] if idx - 2 < len(chunks) else []
        if not chunk:
            chunk = [
                "Conteúdo de apoio pendente para esta página.",
                "Insira aqui os tópicos técnicos do módulo correspondente.",
            ]
        bullets = "\n".join([f"• {item}" for item in chunk[:6]])
        frames.append(
            DesignFrame(
                id=f"page-{idx}",
                name=f"Página {idx}",
                background="#FFFFFF",
                elements=[
                    make_rect_element(
                        element_id=f"header-{idx}",
                        x=0,
                        y=0,
                        width=canvas.width,
                        height=210,
                        fill="#0F172A",
                    ),
                    make_text_element(
                        element_id=f"title-{idx}",
                        text=f"Módulo {idx - 1}",
                        x=140,
                        y=54,
                        width=canvas.width - 280,
                        height=110,
                        font_size=56,
                        font_weight="bold",
                        fill="#F8FAFC",
                        text_align="left",
                    ),
                    make_text_element(
                        element_id=f"body-{idx}",
                        text=bullets,
                        x=160,
                        y=320,
                        width=canvas.width - 320,
                        height=canvas.height - 560,
                        font_size=46,
                        font_weight="normal",
                        fill="#111827",
                        text_align="left",
                    ),
                ],
            )
        )

    doc = DesignSourceDocument(
        kind="a4_booklet",
        title=topic,
        canvas=canvas,
        frames=frames,
        metadata={
            "render_engine": "fabric.js",
            "format_profile": "a4_print_300dpi",
            "source": "a4_booklet_generator",
        },
    )
    return serialize_doc(doc)

