from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TemplateFamily = Literal["story", "feed", "a4", "slide"]


class TemplateSelection(BaseModel):
    template_family: TemplateFamily = Field(description="Família do template selecionado.")
    template_id: str = Field(description="ID estável do template selecionado.")
    template_label: str = Field(description="Nome amigável do template selecionado.")
    canvas_preset: str | None = Field(default=None, description="Preset visual associado ao template.")


class SlotUpdateSet(BaseModel):
    slot_updates: dict[str, str] = Field(
        default_factory=dict,
        description="Mapa semântico slot -> valor. Não usa seletor CSS cru."
    )
