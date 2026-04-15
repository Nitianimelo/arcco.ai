"""
Skill: Gerador de Reels/Stories (Design Source)
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
    "id": "reels_story_generator",
    "name": "Gerador de Reels/Stories",
    "description": (
        "Gera design source para formato vertical 1080x1920 (Reels e Stories), "
        "em sequência de frames quando necessário."
    ),
    # Desativado: supersedido por story_reel_creator (HTML direto).
    "keywords": ["reels_canvas_source_internal"],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Tema principal."},
            "context_data": {"type": "string", "description": "Roteiro/copy de apoio."},
            "frame_count": {"type": "integer", "description": "Quantidade de frames."},
        },
        "required": ["topic"],
    },
}


async def execute(args: dict) -> str:
    topic = safe_title(str(args.get("topic", "")), "Reels / Stories")
    context_data = str(args.get("context_data", "") or "")
    requested_frames = int(args.get("frame_count", 3) or 3)
    frame_count = clamp_int(requested_frames, 1, 10)

    canvas = canvas_from_preset("reels_story")
    points = extract_points(context_data, max_points=40)
    chunks = enumerate_chunks(points, 2) if points else []

    frames: list[DesignFrame] = []
    for i in range(frame_count):
        chunk = chunks[i] if i < len(chunks) else []
        if not chunk:
            chunk = ["Adicione roteiro curto para este frame."]
        text_block = "\n".join(chunk[:2])
        frames.append(
            DesignFrame(
                id=f"frame-{i + 1}",
                name=f"Frame {i + 1}",
                background="#0B1020",
                elements=[
                    make_rect_element(
                        element_id=f"surface-{i + 1}",
                        x=60,
                        y=120,
                        width=canvas.width - 120,
                        height=canvas.height - 260,
                        fill="#111827",
                        corner_radius=34,
                    ),
                    make_text_element(
                        element_id=f"topic-{i + 1}",
                        text=(topic if i == 0 else f"Sequência {i + 1}"),
                        x=120,
                        y=220,
                        width=canvas.width - 240,
                        height=220,
                        font_size=74,
                        font_weight="bold",
                        fill="#F8FAFC",
                        text_align="left",
                    ),
                    make_text_element(
                        element_id=f"body-{i + 1}",
                        text=text_block,
                        x=120,
                        y=560,
                        width=canvas.width - 240,
                        height=500,
                        font_size=48,
                        fill="#E2E8F0",
                        text_align="left",
                    ),
                    make_text_element(
                        element_id=f"indicator-{i + 1}",
                        text=f"{i + 1}/{frame_count}",
                        x=820,
                        y=1760,
                        width=180,
                        height=80,
                        font_size=34,
                        font_weight="bold",
                        fill="#93C5FD",
                        text_align="right",
                    ),
                ],
            )
        )

    doc = DesignSourceDocument(
        kind="reels_story",
        title=topic,
        canvas=canvas,
        frames=frames,
        metadata={
            "render_engine": "fabric.js",
            "format_profile": "vertical_9_16",
            "source": "reels_story_generator",
        },
    )
    return serialize_doc(doc)

