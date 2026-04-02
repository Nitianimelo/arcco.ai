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
from backend.services.design_template_registry import (
    build_slot_defaults,
    infer_template_family,
    pick_design_template,
)
from backend.services.unsplash import build_unsplash_url

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
    canvas_preset: Optional[str] = Field(default=None, description="Preset interno sugerido. Ex: ig-story ou ig-post-square.")
    visual_goal: str = Field(description="Objetivo da peça. Ex: captar atenção, converter, educar, anunciar.")
    art_direction: str = Field(description="Direção estética resumida em 1-2 frases.")
    palette: List[str] = Field(description="Paleta principal em hex ou nomes curtos.")
    typography: str = Field(description="Orientação tipográfica resumida.")
    layout_strategy: str = Field(description="Como distribuir os elementos no canvas.")
    blocks: List[VisualBlock] = Field(description="Blocos principais da peça em ordem de prioridade.")
    background_idea: Optional[str] = Field(default=None, description="Ideia visual para o fundo.")
    decorative_elements: List[str] = Field(default_factory=list, description="Ícones, shapes ou elementos decorativos.")
    template_family: Optional[Literal["story", "feed", "a4", "slide"]] = Field(default=None, description="Família de template determinístico, quando houver.")
    template_id: Optional[str] = Field(default=None, description="ID do template determinístico escolhido.")
    template_label: Optional[str] = Field(default=None, description="Nome amigável do template escolhido.")
    template_css_class: Optional[str] = Field(default=None, description="Classe CSS-base do template, quando aplicável.")
    image_provider: Optional[Literal["unsplash"]] = Field(default=None, description="Provedor de imagem recomendado.")
    image_query: Optional[str] = Field(default=None, description="Query de imagem sugerida para preencher o template.")
    image_url: Optional[str] = Field(default=None, description="URL pronta de imagem para o template, se disponível.")
    slot_updates: dict[str, str] = Field(default_factory=dict, description="Mapa semântico de slots para preenchimento do template.")


def _default_image_query(topic: str, context_data: str, template: dict | None) -> str:
    base = (topic or "").strip()
    if template and template.get("default_image_query"):
        default = str(template["default_image_query"]).strip()
        if base:
            return f"{base}, {default}"
        return default
    if context_data:
        trimmed = context_data.strip().replace("\n", " ")
        return f"{base}, {trimmed[:80]}".strip(", ")
    return base or "premium editorial story background"


def _build_fallback_spec(topic: str, format_hint: str, context_data: str) -> StaticDesignSpec:
    title = topic.strip() or "Peça visual"
    palette = ["#0F172A", "#E2E8F0", "#38BDF8"]
    if "páscoa" in topic.lower() or "pascoa" in topic.lower():
        palette = ["#7C5C3B", "#F4E6C8", "#D9B99B"]
    template_family = infer_template_family(topic, format_hint, context_data)
    template = pick_design_template(topic, template_family, context_data, format_hint)
    image_query = _default_image_query(topic, context_data, template)
    image_size = (1080, 1920) if template_family == "story" else (1080, 1350 if template_family == "feed" and "1350" in (template or {}).get("format", "") else 1080)
    image_url = (
        build_unsplash_url(image_query, width=image_size[0], height=image_size[1])
        if template and template.get("requires_image")
        else None
    )
    return StaticDesignSpec(
        title=title[:90],
        format=((template or {}).get("format") or (format_hint or "1080x1080")),
        canvas_preset=(template or {}).get("canvas_preset"),
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
        template_family=template_family if template else None,
        template_id=(template or {}).get("id"),
        template_label=(template or {}).get("label"),
        template_css_class=(template or {}).get("css_class"),
        image_provider=("unsplash" if image_url else None),
        image_query=(image_query if image_url else None),
        image_url=image_url,
        slot_updates=build_slot_defaults(topic, context_data, template),
    )


_SYSTEM_PROMPT = """Você é Diretor de Arte e Designer de Performance especializado em peças de canvas único.

Sua missão é transformar um briefing solto em uma especificação visual extremamente clara para um gerador HTML.

REGRAS:
- Pense apenas em UMA peça por vez.
- Otimize para impacto imediato e leitura rápida.
- Organize a informação em blocos visuais com prioridade.
- Evite poluição: poucos blocos, hierarquia forte, CTA claro quando fizer sentido.
- Não escreva HTML. Seu trabalho é devolver o briefing visual estruturado em JSON.
- Sempre prefira um template determinístico quando houver catálogo disponível para a família correta: story, feed, a4 ou slide.
- Devolva template_family, template_id, template_label, canvas_preset e slot_updates semânticos.
- Quando a composição pedir fotografia, devolva image_query e image_url do Unsplash.
- Se houver template determinístico indicado, respeite sua lógica visual em vez de inventar um layout totalmente novo.

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

    template_family = infer_template_family(topic, format_hint, context_data)
    template = pick_design_template(topic, template_family, context_data, format_hint)
    if template:
        image_query = _default_image_query(topic, context_data, template)
        user_content += (
            "\n\nCATÁLOGO DETERMINÍSTICO DISPONÍVEL:\n"
            f"- família: {template_family}\n"
            f"- template_id recomendado: {template['id']}\n"
            f"- label: {template['label']}\n"
            f"- categoria: {template.get('category', '')}\n"
            f"- descrição: {template.get('description', '')}\n"
            f"- formato: {template.get('format', '')}\n"
            f"- canvas_preset: {template.get('canvas_preset', '')}\n"
            f"- slots: {', '.join(template.get('slots', []))}\n"
            f"- slot_updates base: {json.dumps(build_slot_defaults(topic, context_data, template), ensure_ascii=False)}\n"
            f"- use fotografia do Unsplash quando fizer sentido com a query: {image_query}\n"
            "- se usar imagem, devolva também image_url otimizada para o formato do template.\n"
        )

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
        if template:
            if not spec.template_id:
                spec.template_family = template_family
                spec.template_id = str(template["id"])
                spec.template_label = str(template["label"])
                spec.template_css_class = str(template.get("css_class", ""))
            if not spec.canvas_preset:
                spec.canvas_preset = str(template.get("canvas_preset", ""))
            if not spec.image_query:
                spec.image_query = _default_image_query(topic, context_data, template)
            if not spec.image_url and template.get("requires_image"):
                spec.image_provider = "unsplash"
                width, height = (1080, 1920) if template_family == "story" else (1080, 1350 if template_family == "feed" and "1350" in str(template.get("format", "")) else 1080)
                spec.image_url = build_unsplash_url(spec.image_query or topic, width=width, height=height)
            if not spec.format:
                spec.format = str(template.get("format", format_hint or "1080x1080"))
            if not spec.slot_updates:
                spec.slot_updates = build_slot_defaults(topic, context_data, template)
        logger.info("[STATIC_DESIGN_GENERATOR] Spec gerado: '%s' | formato: %s", spec.title, spec.format)
        return spec.model_dump_json(ensure_ascii=False)
    except Exception as exc:
        logger.warning("[STATIC_DESIGN_GENERATOR] Fallback local acionado para '%s': %s", topic[:60], exc)
        fallback = _build_fallback_spec(topic, format_hint, context_data)
        return fallback.model_dump_json(ensure_ascii=False)
