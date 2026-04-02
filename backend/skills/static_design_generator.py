"""
Skill: Gerador de Design Estático (Single Canvas Design Brief)

Gera um briefing visual estruturado em JSON para peças de canvas único:
- post estático para Instagram
- banner
- flyer
- capa
- thumb/thumbnail
- story único

Fluxo ideal no Planner:
  static_design_generator → design_generator (terminal)
"""

import asyncio
import json
import logging
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)
_STATIC_DESIGN_LLM_TIMEOUT_SECONDS = 24.0


SKILL_META = {
    "id": "static_design_generator",
    "name": "Gerador de Design Estático",
    "description": (
        "Cria um briefing visual estruturado em JSON para uma única peça gráfica: post estático, "
        "banner, flyer, capa, thumbnail ou story. "
        "Use ANTES do design_generator quando o pedido for uma peça única e não uma sequência de slides."
    ),
    "keywords": [
        "post", "banner", "flyer", "capa", "thumb", "thumbnail", "story",
        "instagram", "arte", "criativo", "peça visual", "peca visual", "anúncio", "anuncio"
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema principal da peça"
            },
            "format_hint": {
                "type": "string",
                "description": "Formato desejado, se já souber (ex: 1080x1080, 1080x1350, 1920x1080)"
            },
            "context_data": {
                "type": "string",
                "description": "Informações adicionais, copy, briefing de marca ou dados coletados antes"
            }
        },
        "required": ["topic"]
    }
}


class VisualBlock(BaseModel):
    type: Literal["headline", "subheadline", "body", "highlight", "cta", "badge", "icon_cluster"] = Field(
        description="Tipo de bloco visual no canvas."
    )
    content: str = Field(description="Texto bruto ou intenção do bloco.")
    priority: Literal["high", "medium", "low"] = Field(description="Prioridade visual do bloco no layout.")


class StaticDesignSpec(BaseModel):
    title: str = Field(description="Nome da peça visual.")
    format: str = Field(description="Formato/canvas sugerido. Ex: 1080x1080, 1080x1350.")
    visual_goal: str = Field(description="Objetivo da peça. Ex: captar atenção, converter, educar, anunciar.")
    art_direction: str = Field(description="Direção estética resumida em 1-2 frases.")
    palette: List[str] = Field(description="Paleta principal em hex ou nomes curtos.")
    typography: str = Field(description="Orientação tipográfica resumida.")
    layout_strategy: str = Field(description="Como distribuir os elementos no canvas.")
    blocks: List[VisualBlock] = Field(description="Blocos principais da peça em ordem de prioridade.")
    background_idea: Optional[str] = Field(default=None, description="Ideia visual para o fundo.")
    decorative_elements: List[str] = Field(default_factory=list, description="Ícones, shapes ou elementos decorativos.")


def _build_fallback_spec(topic: str, format_hint: str, context_data: str) -> StaticDesignSpec:
    title = topic.strip() or "Peça visual"
    palette = ["#0F172A", "#E2E8F0", "#38BDF8"]
    if "páscoa" in topic.lower() or "pascoa" in topic.lower():
        palette = ["#7C5C3B", "#F4E6C8", "#D9B99B"]
    return StaticDesignSpec(
        title=title[:90],
        format=(format_hint or "1080x1080"),
        visual_goal="Captar atenção com leitura rápida e hierarquia clara.",
        art_direction="Visual limpo, contraste forte e foco no headline principal.",
        palette=palette,
        typography="Sans-serif forte no título e apoio neutro no restante.",
        layout_strategy="Headline dominante, apoio curto abaixo e CTA em bloco separado no rodapé.",
        blocks=[
            VisualBlock(type="headline", content=title[:90], priority="high"),
            VisualBlock(type="subheadline", content=(context_data.strip()[:140] or "Mensagem principal da peça."), priority="medium"),
            VisualBlock(type="cta", content="Edite a marca e a chamada para ação no fechamento.", priority="medium"),
        ],
        background_idea="Gradiente sutil com textura leve ou formas geométricas amplas.",
        decorative_elements=["shape abstrato", "ícone temático discreto"],
    )


_SYSTEM_PROMPT = """Você é Diretor de Arte e Designer de Performance especializado em peças de canvas único.

Sua missão é transformar um briefing solto em uma especificação visual extremamente clara para um gerador HTML.

REGRAS:
- Pense apenas em UMA peça por vez.
- Otimize para impacto imediato e leitura rápida.
- Organize a informação em blocos visuais com prioridade.
- Evite poluição: poucos blocos, hierarquia forte, CTA claro quando fizer sentido.
- Não escreva HTML. Seu trabalho é devolver o briefing visual estruturado em JSON.

Retorne APENAS JSON válido, sem markdown."""


async def execute(args: dict) -> str:
    topic = args.get("topic", "Peça visual")
    format_hint = args.get("format_hint", "").strip()
    context_data = args.get("context_data", "").strip()

    schema = StaticDesignSpec.model_json_schema()
    system_with_schema = (
        _SYSTEM_PROMPT
        + f"\n\nOUTPUT SCHEMA OBRIGATÓRIO (retorne APENAS o JSON válido):\n{json.dumps(schema)}"
    )

    user_content = f"Crie o briefing visual estruturado para: {topic}"
    if format_hint:
        user_content += f"\nFormato desejado: {format_hint}"
    if context_data:
        user_content += f"\n\nContexto adicional:\n{context_data}"

    model = (
        registry.get_model("static_design_generator")
        or registry.get_model("text_generator")
        or "openai/gpt-4o-mini"
    )
    logger.info("[STATIC_DESIGN_GENERATOR] Gerando spec para: '%s' | modelo: %s", topic[:60], model)

    try:
        data = await asyncio.wait_for(
            call_openrouter(
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user", "content": user_content},
                ],
                model=model,
                max_tokens=1600,
                temperature=0.3,
                timeout_seconds=_STATIC_DESIGN_LLM_TIMEOUT_SECONDS,
            ),
            timeout=_STATIC_DESIGN_LLM_TIMEOUT_SECONDS + 2.0,
        )

        raw = data["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("\n", 1)[0]

        parsed = json.loads(raw)
        spec = StaticDesignSpec.model_validate(parsed)
        logger.info("[STATIC_DESIGN_GENERATOR] Spec gerado: '%s' | formato: %s", spec.title, spec.format)
        return spec.model_dump_json(ensure_ascii=False)
    except Exception as exc:
        logger.warning("[STATIC_DESIGN_GENERATOR] Fallback local acionado para '%s': %s", topic[:60], exc)
        fallback = _build_fallback_spec(topic, format_hint, context_data)
        return fallback.model_dump_json(ensure_ascii=False)
