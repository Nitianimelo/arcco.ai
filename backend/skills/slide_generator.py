"""
Skill: Gerador de Slides (Slide Deck Generator)

Atua como Copywriter Sênior + Designer de UX simultaneamente.
Produz uma estrutura JSON completa (SlideDeck) que o design_generator
usa para renderizar uma apresentação HTML de alto impacto.

Fluxo ideal no Planner:
  web_search → slide_generator → design_generator (terminal)
"""

import json
import logging
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

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
        "powerpoint", "pptx", "keynote", "palestra", "deck de vendas", "slideshow"
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
    slides: List[Slide] = Field(
        description="Lista de slides com a narrativa completa. Mínimo 6, máximo 14 slides."
    )


# ── Execução da Skill ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Você é um Designer de UX e Copywriter Sênior com experiência em apresentações nível Apple Keynote e decks McKinsey.

Sua missão: criar uma apresentação de slides de alto impacto que conta uma história clara e persuasiva.

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

    user_content = f"Crie uma apresentação sobre: {topic}"
    if context_data:
        user_content += f"\n\nDados de contexto para embasar os slides:\n{context_data}"

    model = registry.get_model("text_generator") or "openai/gpt-4o-mini"
    logger.info("[SLIDE_GENERATOR] Gerando deck para: '%s' | modelo: %s", topic[:60], model)

    data = await call_openrouter(
        messages=[
            {"role": "system", "content": system_with_schema},
            {"role": "user",   "content": user_content},
        ],
        model=model,
        max_tokens=3000,
        temperature=0.7,
    )

    raw = data["choices"][0]["message"]["content"].strip()

    # Strip markdown backticks (mesmo padrão do planner.py)
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("\n", 1)[0]

    parsed = json.loads(raw)
    deck = SlideDeck.model_validate(parsed)

    slide_count = len(deck.slides)
    logger.info("[SLIDE_GENERATOR] Deck gerado: '%s' | %d slides", deck.title, slide_count)

    return deck.model_dump_json(ensure_ascii=False)
