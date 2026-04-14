"""
Contrato estruturado de design (fonte da verdade) para render e export.

Este contrato evita HTML livre como payload primário. O renderer converte
este source para Fabric JSON/canvas no frontend e no backend.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


CanvasPreset = Literal[
    "a4_booklet",
    "slide_widescreen",
    "instagram_post",
    "reels_story",
]

DesignKind = Literal[
    "a4_booklet",
    "slide_presentation",
    "instagram_post",
    "reels_story",
]


CANVAS_PRESETS: dict[CanvasPreset, dict[str, int | str]] = {
    # A4 em 300 DPI (impressão)
    "a4_booklet": {"width": 2480, "height": 3508, "dpi": 300, "unit": "px"},
    # Slides e social em pixel screen
    "slide_widescreen": {"width": 1920, "height": 1080, "dpi": 96, "unit": "px"},
    "instagram_post": {"width": 1080, "height": 1080, "dpi": 96, "unit": "px"},
    "reels_story": {"width": 1080, "height": 1920, "dpi": 96, "unit": "px"},
}


class DesignElement(BaseModel):
    id: str
    type: Literal["text", "rect"] = "text"
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 40
    rotation: float = 0
    opacity: float = 1
    fill: str = "#111827"
    stroke: Optional[str] = None
    stroke_width: float = 0
    corner_radius: float = 0
    text: Optional[str] = None
    font_family: str = "Arial"
    font_size: int = 32
    font_weight: str = "normal"
    text_align: Literal["left", "center", "right", "justify"] = "left"
    line_height: float = 1.2


class DesignFrame(BaseModel):
    id: str
    name: str
    background: str = "#FFFFFF"
    notes: Optional[str] = None
    elements: list[DesignElement] = Field(default_factory=list)


class DesignCanvas(BaseModel):
    preset: CanvasPreset
    width: int
    height: int
    dpi: int
    unit: Literal["px"] = "px"


class DesignSourceDocument(BaseModel):
    schema_version: Literal["arcco.design-source/v1"] = "arcco.design-source/v1"
    kind: DesignKind
    title: str
    canvas: DesignCanvas
    frames: list[DesignFrame]
    metadata: dict[str, str] = Field(default_factory=dict)


def canvas_from_preset(preset: CanvasPreset) -> DesignCanvas:
    spec = CANVAS_PRESETS[preset]
    return DesignCanvas(
        preset=preset,
        width=int(spec["width"]),
        height=int(spec["height"]),
        dpi=int(spec["dpi"]),
        unit=str(spec["unit"]),
    )


def make_text_element(
    *,
    element_id: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: int = 48,
    font_weight: str = "bold",
    fill: str = "#0F172A",
    text_align: Literal["left", "center", "right", "justify"] = "left",
) -> DesignElement:
    return DesignElement(
        id=element_id,
        type="text",
        x=x,
        y=y,
        width=width,
        height=height,
        text=text,
        font_size=font_size,
        font_weight=font_weight,
        fill=fill,
        text_align=text_align,
    )


def make_rect_element(
    *,
    element_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    fill: str = "#E2E8F0",
    stroke: Optional[str] = None,
    stroke_width: float = 0,
    corner_radius: float = 0,
    opacity: float = 1,
) -> DesignElement:
    return DesignElement(
        id=element_id,
        type="rect",
        x=x,
        y=y,
        width=width,
        height=height,
        fill=fill,
        stroke=stroke,
        stroke_width=stroke_width,
        corner_radius=corner_radius,
        opacity=opacity,
    )


def frame_to_fabric_json(frame: DesignFrame, canvas: DesignCanvas) -> dict:
    objects: list[dict] = []
    for element in frame.elements:
        if element.type == "text":
            objects.append(
                {
                    "type": "textbox",
                    "left": element.x,
                    "top": element.y,
                    "width": element.width,
                    "height": element.height,
                    "angle": element.rotation,
                    "opacity": element.opacity,
                    "fill": element.fill,
                    "text": element.text or "",
                    "fontFamily": element.font_family,
                    "fontSize": element.font_size,
                    "fontWeight": element.font_weight,
                    "textAlign": element.text_align,
                    "lineHeight": element.line_height,
                    "editable": False,
                    "selectable": False,
                }
            )
            continue

        if element.type == "rect":
            objects.append(
                {
                    "type": "rect",
                    "left": element.x,
                    "top": element.y,
                    "width": element.width,
                    "height": element.height,
                    "angle": element.rotation,
                    "opacity": element.opacity,
                    "fill": element.fill,
                    "stroke": element.stroke,
                    "strokeWidth": element.stroke_width,
                    "rx": element.corner_radius,
                    "ry": element.corner_radius,
                    "selectable": False,
                }
            )

    return {
        "version": "5.3.0",
        "background": frame.background,
        "objects": objects,
        "clipPath": {
            "type": "rect",
            "left": 0,
            "top": 0,
            "width": canvas.width,
            "height": canvas.height,
            "absolutePositioned": True,
            "selectable": False,
            "evented": False,
        },
    }

