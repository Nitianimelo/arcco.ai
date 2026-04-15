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
from backend.services.design_template_registry import build_guided_design_contract, build_slot_defaults, choose_design_route

logger = logging.getLogger(__name__)
_SLIDE_LLM_TIMEOUT_SECONDS = 45.0
_DEFAULT_SLIDE_COUNT = 8
_MIN_FALLBACK_SLIDES = 4
_MAX_FALLBACK_SLIDES = 18

_EXPLICIT_COUNT_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"(\d{1,2})\s*slides?", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*(?:tend[eê]ncias?|tópicos?|topicos?|itens?|pontos?|bullets?)", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*(?:cards?|páginas?|paginas?)", re.IGNORECASE),
)


def _infer_requested_slide_count(topic: str, context_data: str) -> int | None:
    """Detecta quando o usuário pediu explicitamente um número de slides/itens."""
    haystack = f"{topic or ''}\n{context_data or ''}"
    for pattern in _EXPLICIT_COUNT_PATTERNS:
        match = pattern.search(haystack)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 30:
                    return value
            except ValueError:
                continue
    return None

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
    # Desativado: supersedido por presentation_slides_creator (HTML direto).
    # Manter para uso interno quando pipeline JSON→design_generator for preferível.
    "keywords": ["slide_json_structure_internal"],
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
    chart_type: Optional[Literal["bar", "line", "doughnut"]] = Field(
        default=None,
        description=(
            "Use SOMENTE quando houver comparação, evolução temporal ou distribuição com números explícitos no contexto. "
            "Tipos aceitos: 'bar', 'line' ou 'doughnut'."
        ),
    )
    chart_title: Optional[str] = Field(
        default=None,
        description="Título curto do gráfico, quando chart_type estiver preenchido.",
    )
    chart_labels: List[str] = Field(
        default_factory=list,
        description="Rótulos do eixo/categorias do gráfico. Máximo de 6 itens.",
    )
    chart_values: List[float] = Field(
        default_factory=list,
        description="Valores numéricos do gráfico, na mesma ordem de chart_labels.",
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
    style_overrides: dict[str, str] = Field(default_factory=dict, description="Overrides de estilo permitidos sobre o template base.")
    allowed_edits: List[str] = Field(default_factory=list, description="Áreas que podem ser alteradas no modo guided.")
    optional_blocks: List[str] = Field(default_factory=list, description="Blocos opcionais que podem ser ligados ou omitidos.")
    locked_regions: List[str] = Field(default_factory=list, description="Regiões estruturais que não devem ser quebradas.")
    slides: List[Slide] = Field(
        description="Lista de slides com a narrativa completa. Para carrossel de Instagram, normalmente 3-8 slides. Para apresentações, 6-14 slides."
    )


def _clean_line(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned.strip(" -•*")


def _extract_points(context_data: str, max_points: int = 60) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", context_data or "")
    points: list[str] = []
    for part in raw_parts:
        cleaned = _clean_line(part)
        if len(cleaned) < 18:
            continue
        if cleaned not in points:
            points.append(cleaned[:220])
        if len(points) >= max_points:
            break
    return points


def _chunk_points_into_slides(points: list[str], slide_count: int, bullets_per_slide: int = 3) -> list[list[str]]:
    """Distribui pontos extraídos entre N slides de conteúdo."""
    if slide_count <= 0:
        return []
    buckets: list[list[str]] = [[] for _ in range(slide_count)]
    for index, point in enumerate(points):
        bucket_index = index % slide_count
        if len(buckets[bucket_index]) < bullets_per_slide:
            buckets[bucket_index].append(point)
    return buckets


def _build_fallback_deck(topic: str, context_data: str) -> SlideDeck:
    points = _extract_points(context_data)
    short_topic = _clean_line(topic)[:72] or "Apresentação"
    selection = choose_design_route(topic, "slide", context_data, "16:9")
    template = selection["template"]

    requested_count = _infer_requested_slide_count(topic, context_data)
    if requested_count:
        total_slides = requested_count
    elif points:
        # Estima baseado no volume de pontos: ~3 bullets por slide + capa + fecho.
        estimated_content_slides = max(3, (len(points) + 2) // 3)
        total_slides = min(_MAX_FALLBACK_SLIDES, max(_MIN_FALLBACK_SLIDES, estimated_content_slides + 2))
    else:
        total_slides = _DEFAULT_SLIDE_COUNT

    total_slides = max(_MIN_FALLBACK_SLIDES, min(_MAX_FALLBACK_SLIDES, total_slides))

    # Capa + Conteúdo + Fecho.
    content_slide_count = max(1, total_slides - 2)
    buckets = _chunk_points_into_slides(points, content_slide_count, bullets_per_slide=3)

    slides: list[Slide] = [
        Slide(
            layout="title_and_subtitle",
            heading=short_topic[:48],
            points=[],
            big_value=None,
            speaker_notes=(
                "Apresente o tema com contexto rápido, destaque por que ele importa agora "
                "e prepare a transição para os pontos principais."
            ),
        )
    ]
    for idx, bucket in enumerate(buckets, start=1):
        if bucket:
            slides.append(
                Slide(
                    layout="bullets",
                    heading=f"Ponto {idx}",
                    points=bucket,
                    big_value=None,
                    speaker_notes=(
                        "Explique os pontos em sequência curta, priorizando os dados mais concretos "
                        "coletados nos passos anteriores."
                    ),
                )
            )
        else:
            # Sem dados reais: ainda entrega a estrutura mas sinaliza gap no speaker_notes.
            slides.append(
                Slide(
                    layout="bullets",
                    heading=f"Ponto {idx}",
                    points=[
                        "Gap de dados: complete com informação verificada antes de apresentar.",
                    ],
                    big_value=None,
                    speaker_notes=(
                        "Este slide ficou sem conteúdo concreto porque a pesquisa anterior não "
                        "retornou dados suficientes. Evite apresentar até completar com fonte real."
                    ),
                )
            )

    slides.append(
        Slide(
            layout="title_and_subtitle",
            heading="Conclusão",
            points=[],
            big_value=None,
            speaker_notes="Feche com síntese, consequência prática e um próximo passo claro para o público.",
        )
    )

    # Garante exatamente o total solicitado (ajuste fino após montagem).
    if len(slides) > total_slides:
        slides = slides[:total_slides - 1] + [slides[-1]]
    elif len(slides) < total_slides:
        while len(slides) < total_slides:
            slides.insert(
                len(slides) - 1,
                Slide(
                    layout="bullets",
                    heading=f"Ponto adicional {len(slides)}",
                    points=["Gap de dados: complemente antes de apresentar."],
                    big_value=None,
                    speaker_notes="Slide gerado para respeitar a quantidade pedida; preencher com dados reais antes do uso.",
                ),
            )

    guided_contract = build_guided_design_contract(topic, context_data, template, str(selection["mode"]))
    return SlideDeck(
        title=short_topic,
        template_family="slide" if template else None,
        template_id=(template or {}).get("id"),
        template_label=(template or {}).get("label"),
        canvas_preset=(template or {}).get("canvas_preset"),
        render_mode=str(selection["mode"]),
        template_score=int(selection.get("score", -1) or 0),
        # IMPORTANTE: NÃO chamamos build_slot_defaults porque ele retorna placeholders
        # genéricos ("Backbone", "73%", "Ponto 1 | Ponto 2 | Ponto 3") que contaminam o deck.
        slot_updates={},
        style_overrides=guided_contract["style_overrides"],
        allowed_edits=guided_contract["allowed_edits"],
        optional_blocks=guided_contract["optional_blocks"],
        locked_regions=guided_contract["locked_regions"],
        slides=slides,
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
- Só preencha chart_type/chart_title/chart_labels/chart_values quando o contexto trouxer números claros e comparáveis.
- Nunca invente números precisos para preencher gráfico. Se os dados não existirem, deixe os campos de gráfico vazios.

REGRAS DE COPY:
- Headings: máx 6 palavras, verbos de ação, sem pontuação final
- Points (bullets): concisos, paralelos entre si, sem verbo auxiliar no início
- Speaker notes: roteiro completo, tom conversacional, inclui transição para próximo slide
- Prefira template determinístico da família slide quando houver catálogo disponível.
- Retorne template_family, template_id, template_label, canvas_preset e slot_updates globais do deck.
- Quando render_mode for guided, retorne também style_overrides, allowed_edits, optional_blocks e locked_regions.
- Se um slide trouxer gráfico, mantenha no máximo 4 labels em bar/doughnut e 6 labels em line.

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
            f"- guided_contract base: {json.dumps(build_guided_design_contract(topic, context_data, template, str(selection.get('mode'))), ensure_ascii=False)}\n"
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
            guided_contract = build_guided_design_contract(topic, context_data, template, str(selection["mode"]))
            if not deck.style_overrides:
                deck.style_overrides = guided_contract["style_overrides"]
            if not deck.allowed_edits:
                deck.allowed_edits = guided_contract["allowed_edits"]
            if not deck.optional_blocks:
                deck.optional_blocks = guided_contract["optional_blocks"]
            if not deck.locked_regions:
                deck.locked_regions = guided_contract["locked_regions"]
        else:
            deck.template_family = None
            deck.template_id = None
            deck.template_label = None

        slide_count = len(deck.slides)
        logger.info(
            "[SLIDE_GENERATOR] branch=llm | modelo=%s | topic='%s' | %d slides",
            model,
            deck.title,
            slide_count,
        )
        return deck.model_dump_json(ensure_ascii=False)
    except Exception as exc:
        logger.warning(
            "[SLIDE_GENERATOR] branch=fallback | modelo=%s | topic='%s' | erro=%s",
            model,
            topic[:60],
            exc,
        )
        fallback = _build_fallback_deck(topic, context_data)
        logger.info(
            "[SLIDE_GENERATOR] fallback gerou %d slides (requested=%s)",
            len(fallback.slides),
            _infer_requested_slide_count(topic, context_data),
        )
        return fallback.model_dump_json(ensure_ascii=False)
