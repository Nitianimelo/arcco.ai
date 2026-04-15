"""
Skill: presentation_slides_creator
Gera uma apresentação de slides 16:9 em HTML de alta qualidade visual.
Retorna HTML puro (<!DOCTYPE html>) que o orchestrator emite como design_artifact.
"""

from __future__ import annotations

import asyncio

from backend.agents import registry
from backend.core.llm import call_openrouter
from backend.services.unsplash_service import enrich_design_instruction

# ── Configuração ──────────────────────────────────────────────────────────────

_TIMEOUT = 150.0
_DEFAULT_SLIDE_COUNT = 8
_MAX_CONTEXT_CHARS = 3000

SKILL_META: dict = {
    "id": "presentation_slides_creator",
    "name": "Criador de Apresentação Visual",
    "description": (
        "Cria uma apresentação de slides widescreen (16:9 / 1920×1080px) em HTML de alta qualidade visual, "
        "pronta para preview imediato no chat. Gera múltiplos slides com design premium (dark theme, "
        "tipografia forte, acento azul) — tema título, conteúdo, dados e encerramento. "
        "Use quando o usuário pedir apresentação, slides, pitch deck, palestra, PowerPoint ou deck visual."
    ),
    "keywords": [
        "apresentação", "apresentacao", "slides", "slide", "pitch", "deck",
        "palestra", "powerpoint", "pptx", "keynote", "slide deck", "deck visual",
        "apresentação visual", "slides visuais",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema ou título da apresentação",
            },
            "context_data": {
                "type": "string",
                "description": "Conteúdo, pesquisa ou dados coletados nos passos anteriores",
            },
            "slide_count": {
                "type": "integer",
                "description": "Número de slides desejado (padrão: 8)",
            },
        },
        "required": ["topic"],
    },
}

# ── Prompt visual ──────────────────────────────────────────────────────────────

_VISUAL_PROMPT = """\
Crie uma apresentação completa de {slide_count} slides sobre "{topic}" em HTML puro de alta qualidade visual.

════════════════════════════════════════
SAÍDA OBRIGATÓRIA
════════════════════════════════════════
• Retorne APENAS o HTML completo. Comece com <!DOCTYPE html>.
• Não use markdown, blocos de código ou qualquer texto fora do HTML.

════════════════════════════════════════
ESTRUTURA HTML
════════════════════════════════════════
• Cada slide = uma tag <section class="slide">
• CSS obrigatório para cada slide:
  section.slide {{
    width: 1920px;
    height: 1080px;
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
  }}
• Todos os slides ficam empilhados verticalmente no documento (sem display:none)
• O DesignGallery do frontend mostra um slide por vez — não oculte slides via JS

════════════════════════════════════════
DESIGN VISUAL — REGRAS INEGOCIÁVEIS
════════════════════════════════════════
Tipografia:
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
  font-family: 'Inter', sans-serif;

Paleta dark premium:
  Fundo principal: #0F172A
  Fundo alternativo: #111827
  Texto principal: #F8FAFC
  Texto secundário: #94A3B8
  Acento azul: #3B82F6
  Acento claro: #60A5FA
  Linha decorativa: #1E40AF

Layout: USE EXCLUSIVAMENTE flexbox/grid. NUNCA position:absolute para texto principal.
Padding interno de cada slide: mínimo 80px nas laterais, 60px no topo e base.

════════════════════════════════════════
TIPOS DE SLIDE E ESPECIFICAÇÕES
════════════════════════════════════════

SLIDE 1 — CAPA:
• Fundo: #0F172A com um retângulo decorativo no canto direito (#1E3A8A, opacity 0.4, 600x1080px)
• Linha acento horizontal: 4px sólida #3B82F6, width 120px, margin-bottom 32px
• Título: Inter 800, 88px, #F8FAFC, max 2 linhas
• Subtítulo: Inter 400, 32px, #94A3B8
• Rodapé: "1 / {slide_count}" — Inter 400, 16px, #475569, canto inferior direito

SLIDES DE CONTEÚDO (maioria dos slides):
• Barra lateral esquerda: 8px sólida #3B82F6, height 80%, position absolute left 60px, top 10%
• Headline: Inter 800, 56px, #F8FAFC, padding-left 100px
• Bullets (máx 4 por slide): Inter 400, 30px, #CBD5E1
  - Cada bullet com dot azul (#3B82F6) de 10px antes do texto
  - Espaçamento entre bullets: 24px
• Rodapé: nome do tema (Inter 400, 14px, #475569) | "N / {slide_count}"

SLIDE DE DADOS/MÉTRICAS (quando relevante):
• Número em destaque: Inter 800, 140px, #3B82F6, centralizado
• Unidade/label: Inter 600, 36px, #94A3B8, abaixo do número
• Contexto explicativo: Inter 400, 24px, #CBD5E1

SLIDE DE ENCERRAMENTO (último):
• Fundo: #111827
• Mensagem principal: Inter 800, 72px, #F8FAFC, centralizada
• CTA ou subtítulo: Inter 400, 32px, #94A3B8
• Linha decorativa: 2px #3B82F6, width 200px, centralizada

════════════════════════════════════════
CONTEÚDO / CONTEXTO BASE
════════════════════════════════════════
{context_data}

════════════════════════════════════════
INSTRUÇÃO FINAL
════════════════════════════════════════
Gere {slide_count} slides completos sobre "{topic}". Distribua o conteúdo de forma inteligente:
use os dados do contexto acima quando disponíveis; caso contrário, crie conteúdo plausível e rico.
Cada slide deve ter texto real e relevante — não use placeholder como "Lorem ipsum".
"""

# ── Executor ──────────────────────────────────────────────────────────────────


async def execute(args: dict) -> str:
    topic = (args.get("topic") or "").strip()
    context_data = (args.get("context_data") or "").strip()
    slide_count = max(3, min(20, int(args.get("slide_count") or _DEFAULT_SLIDE_COUNT)))

    if not topic:
        return "Erro: parâmetro 'topic' é obrigatório."

    unsplash_block = await enrich_design_instruction(topic)

    model = registry.get_model("design_generator") or "anthropic/claude-3.5-sonnet"
    system_prompt = registry.get_prompt("design_generator")

    prompt = _VISUAL_PROMPT.format(
        topic=topic,
        context_data=context_data[:_MAX_CONTEXT_CHARS] if context_data else "Nenhum contexto adicional fornecido.",
        slide_count=slide_count,
    ) + unsplash_block

    try:
        data = await asyncio.wait_for(
            call_openrouter(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=8000,
                temperature=0.6,
                timeout_seconds=_TIMEOUT,
            ),
            timeout=_TIMEOUT + 5,
        )
        html = data["choices"][0]["message"]["content"].strip()
        # Remove fence markdown se o modelo retornar ```html ... ```
        if html.startswith("```"):
            lines = html.split("\n")
            html = "\n".join(lines[1:])
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]
            html = html.strip()
        return html
    except asyncio.TimeoutError:
        return "Erro: timeout ao gerar a apresentação visual."
    except Exception as exc:
        return f"Erro ao gerar apresentação visual: {exc}"
