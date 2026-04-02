"""
Skill: Gerador de Slides (Slide Deck Generator)

Atua como Copywriter Sênior + Designer de UX simultaneamente.
Produz uma estrutura JSON completa (SlideDeck) que o design_generator
usa para renderizar uma apresentação HTML de alto impacto.

Fluxo ideal no Planner:
  web_search → slide_generator → design_generator (terminal)
"""

import asyncio
import json
import logging
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from backend.core.llm import call_openrouter
from backend.agents import registry
from backend.services.design_template_registry import build_slot_defaults, choose_design_route

logger = logging.getLogger(__name__)
_SLIDE_LLM_TIMEOUT_SECONDS = 28.0

# ── Contrato da Skill ─────────────────────────────────────────────────────────

SKILL_META = {
    "id": "slide_generator",
    "name": "Gerador de Slides",
    "description": (
        "Cria a estrutura completa de uma apresentação em JSON: layout visual de cada slide, "
        "título, tópicos, dados de impacto e notas do palestrante. "
        "Use ANTES do design_generator para apresentações de alto impacto, pitch decks e relatórios visuais. "
        "O JSON gerado é passado automaticamente ao design_generator para renderizar o HTML final."
    ),
    "keywords": [
        "slide", "slides", "apresentação", "apresentacao", "pitch", "deck",
        "powerpoint", "pptx", "keynote", "palestra", "deck de vendas", "slideshow",
        "carrossel", "carousel", "instagram"
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema ou título da apresentação"
            },
            "context_data": {
                "type": "string",
                "description": "Dados de contexto, pesquisas ou informações coletadas nos passos anteriores do pipeline"
            }
        },
        "required": ["topic"]
    }
}

# ── Modelos Pydantic — estrutura do deck ──────────────────────────────────────

class Slide(BaseModel):
    layout: Literal["title_and_subtitle", "bullets", "big_number"] = Field(
        description=(
            "Decisão de UX do slide. "
            "'title_and_subtitle': capa, transições e encerramento. "
            "'bullets': listas, explicações e comparações (máx 4 pontos). "
            "'big_number': um dado chocante, preço ou estatística de impacto em destaque."
        )
    )
    heading: str = Field(
        description="Título do slide. Máximo 6 palavras. Direto e impactante."
    )
    points: List[str] = Field(
        default_factory=list,
        description="Tópicos do slide. Apenas para layout 'bullets'. Cada ponto: máx 2 linhas."
    )
    big_value: Optional[str] = Field(
        default=None,
        description="O número ou dado em destaque. Preencher SOMENTE se layout for 'big_number'. Ex: '73%', 'R$ 4,2bi', '10x mais rápido'."
    )
    speaker_notes: str = Field(
        description="Roteiro exato e persuasivo para o palestrante ler neste slide. 2-4 frases."
    )


class SlideDeck(BaseModel):
    title: str = Field(
        description="Título do arquivo da apresentação. Conciso e descritivo."
    )
    template_family: Optional[Literal["slide"]] = Field(default=None, description="Família do template determinístico selecionado.")
    template_id: Optional[str] = Field(default=None, description="ID do template selecionado.")
    template_label: Optional[str] = Field(default=None, description="Nome amigável do template selecionado.")
    canvas_preset: Optional[str] = Field(default=None, description="Preset do preview/export associado ao template.")
    render_mode: Optional[Literal["deterministic", "guided", "open"]] = Field(default=None, description="Estratégia de renderização do deck.")
    template_score: Optional[int] = Field(default=None, description="Score de aderência do template selecionado.")
    slot_updates: dict[str, str] = Field(default_factory=dict, description="Slots semânticos globais do deck/template.")
    slides: List[Slide] = Field(
        description="Lista de slides com a narrativa completa. Para carrossel de Instagram, normalmente 3-8 slides. Para apresentações, 6-14 slides."
    )


def _clean_line(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned.strip(" -•*")


def _extract_points(context_data: str, max_points: int = 6) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", context_data or "")
    points: list[str] = []
    for part in raw_parts:
        cleaned = _clean_line(part)
        if len(cleaned) < 18:
            continue
        if cleaned not in points:
            points.append(cleaned[:180])
        if len(points) >= max_points:
            break
    return points


def _build_fallback_deck(topic: str, context_data: str) -> SlideDeck:
    points = _extract_points(context_data)
    selection = choose_design_route(topic, "slide", context_data, "16:9")
    template = selection["template"]
    intro = points[:2] or [
        "Contextualize o tema com clareza e impacto.",
        "Mostre rapidamente por que isso importa agora.",
    ]
    details = points[2:5] or [
        "Destaque os fatos principais em linguagem simples.",
        "Organize os pontos em ordem lógica para leitura rápida.",
        "Mantenha o foco em impacto e consequência.",
    ]
    closing = points[5:6] or [
        "Feche com consequência, próximo passo ou chamada para ação.",
    ]
    short_topic = _clean_line(topic)[:72] or "Apresentação"
    return SlideDeck(
        title=short_topic,
        template_family="slide" if template else None,
        template_id=(template or {}).get("id"),
        template_label=(template or {}).get("label"),
        canvas_preset=(template or {}).get("canvas_preset"),
        render_mode=str(selection["mode"]),
        template_score=int(selection.get("score", -1) or 0),
        slot_updates=build_slot_defaults(topic, context_data, template),
        slides=[
            Slide(
                layout="title_and_subtitle",
                heading=short_topic[:48],
                points=[],
                big_value=None,
                speaker_notes="Apresente o tema com contexto rápido, destaque por que ele importa e prepare a transição para os fatos centrais.",
            ),
            Slide(
                layout="bullets",
                heading="O que aconteceu",
                points=intro + details[:2],
                big_value=None,
                speaker_notes="Explique os fatos centrais em sequência curta, usando apenas os dados mais relevantes para manter clareza e ritmo.",
            ),
            Slide(
                layout="bullets",
                heading="Impactos e próximos passos",
                points=details[2:4] + closing,
                big_value=None,
                speaker_notes="Feche com impacto, consequência e um próximo passo claro para o público.",
            ),
        ],
    )


# ── Execução da Skill ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Você é um Designer de UX e Copywriter Sênior com experiência em apresentações nível Apple Keynote, decks McKinsey e carrosséis de alto impacto para Instagram.

Sua missão: criar uma apresentação de slides de alto impacto que conta uma história clara e persuasiva.

REGRA DE CONTAGEM DE SLIDES:
- Se o pedido mencionar explicitamente 3 slides, 4 slides, 5 slides etc., respeite esse número.
- Se o pedido for um carrossel de Instagram e não informar quantidade, prefira 3 a 6 slides.
- Se o pedido for uma apresentação/deck sem quantidade explícita, use entre 6 e 14 slides.

FRAMEWORK DE STORYTELLING:
- Identifique a intenção (Pitch de vendas / Relatório executivo / Apresentação educacional)
- Aplique a estrutura: Problema → Agravamento → Solução → Prova → Call to Action
- Cada slide deve ter UMA mensagem central — sem poluição visual

REGRAS DE LAYOUT:
- title_and_subtitle: APENAS para capa (slide 1), transições entre seções e encerramento
- bullets: para argumentos, comparações, listas de benefícios (máx 4 pontos por slide)
- big_number: para dados de impacto, estatísticas chocantes, preços, percentuais

REGRAS DE COPY:
- Headings: máx 6 palavras, verbos de ação, sem pontuação final
- Points (bullets): concisos, paralelos entre si, sem verbo auxiliar no início
- Speaker notes: roteiro completo, tom conversacional, inclui transição para próximo slide
- Prefira template determinístico da família slide quando houver catálogo disponível.
- Retorne template_family, template_id, template_label, canvas_preset e slot_updates globais do deck.

Retorne ESTRITAMENTE o JSON válido. Sem markdown, sem explicações fora do JSON."""


async def execute(args: dict) -> str:
    """
    Gera uma estrutura de slide deck completa em JSON validado pelo Pydantic.

    Args:
        args["topic"]: tema da apresentação
        args["context_data"]: dados coletados em steps anteriores (opcional)

    Returns:
        JSON string do SlideDeck validado
    """
    topic = args.get("topic", "Tema não especificado")
    context_data = args.get("context_data", "").strip()

    schema = SlideDeck.model_json_schema()

    system_with_schema = (
        _SYSTEM_PROMPT
        + f"\n\nOUTPUT SCHEMA OBRIGATÓRIO (retorne APENAS o JSON válido):\n{json.dumps(schema)}"
    )

    user_content = f"Crie a estrutura de slides sobre: {topic}"
    if context_data:
        user_content += f"\n\nDados de contexto para embasar os slides:\n{context_data}"
    selection = choose_design_route(topic, "slide", context_data, "16:9")
    template = selection["template"]
    if template:
        user_content += (
            "\n\nTEMPLATE DETERMINÍSTICO DE SLIDE DISPONÍVEL:\n"
            f"- template_id recomendado: {template['id']}\n"
            f"- label: {template['label']}\n"
            f"- descrição: {template.get('description', '')}\n"
            f"- canvas_preset: {template.get('canvas_preset', '')}\n"
            f"- render_mode recomendado: {selection.get('mode')}\n"
            f"- template_score: {selection.get('score', -1)}\n"
            f"- slots: {', '.join(template.get('slots', []))}\n"
            f"- slot_updates base: {json.dumps(build_slot_defaults(topic, context_data, template), ensure_ascii=False)}\n"
        )
    else:
        user_content += (
            "\n\nESTRATÉGIA DE RENDERIZAÇÃO:\n"
            f"- render_mode recomendado: {selection.get('mode')}\n"
            f"- template_score: {selection.get('score', -1)}\n"
            "- não há template com aderência suficiente; preserve liberdade criativa com boa estrutura narrativa.\n"
        )

    model = (
        registry.get_model("slide_generator")
        or registry.get_model("text_generator")
        or "openai/gpt-4o-mini"
    )
    logger.info("[SLIDE_GENERATOR] Gerando deck para: '%s' | modelo: %s", topic[:60], model)

    try:
        data = await asyncio.wait_for(
            call_openrouter(
                messages=[
                    {"role": "system", "content": system_with_schema},
                    {"role": "user",   "content": user_content},
                ],
                model=model,
                max_tokens=2200,
                temperature=0.4,
                timeout_seconds=_SLIDE_LLM_TIMEOUT_SECONDS,
            ),
            timeout=_SLIDE_LLM_TIMEOUT_SECONDS + 2.0,
        )

        raw = data["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("\n", 1)[0]

        parsed = json.loads(raw)
        deck = SlideDeck.model_validate(parsed)
        deck.render_mode = str(selection["mode"])
        deck.template_score = int(selection.get("score", -1) or 0)
        if template:
            if not deck.template_family:
                deck.template_family = "slide"
            if not deck.template_id:
                deck.template_id = str(template["id"])
            if not deck.template_label:
                deck.template_label = str(template["label"])
            if not deck.canvas_preset:
                deck.canvas_preset = str(template.get("canvas_preset", ""))
            if not deck.slot_updates:
                deck.slot_updates = build_slot_defaults(topic, context_data, template)
        else:
            deck.template_family = None
            deck.template_id = None
            deck.template_label = None

        slide_count = len(deck.slides)
        logger.info("[SLIDE_GENERATOR] Deck gerado: '%s' | %d slides", deck.title, slide_count)
        return deck.model_dump_json(ensure_ascii=False)
    except Exception as exc:
        logger.warning("[SLIDE_GENERATOR] Fallback local acionado para '%s': %s", topic[:60], exc)
        fallback = _build_fallback_deck(topic, context_data)
        return fallback.model_dump_json(ensure_ascii=False)
