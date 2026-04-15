"""
Skill: instagram_carousel_creator
Gera um carrossel de posts para Instagram em HTML de alta qualidade visual.
Cada frame é 1080×1080px (section.slide). Retorna HTML puro como design_artifact.
"""

from __future__ import annotations

import asyncio

from backend.agents import registry
from backend.core.llm import call_openrouter
from backend.services.unsplash_service import enrich_design_instruction

# ── Configuração ──────────────────────────────────────────────────────────────

_TIMEOUT = 120.0
_DEFAULT_SLIDE_COUNT = 6
_MAX_CONTEXT_CHARS = 3000

SKILL_META: dict = {
    "id": "instagram_carousel_creator",
    "name": "Criador de Carrossel Instagram",
    "description": (
        "Cria um carrossel de posts para Instagram (1080×1080px por frame) em HTML de alta qualidade visual, "
        "pronto para preview imediato no chat. Estrutura: hook impactante no frame 1, conteúdo educativo/valor "
        "nos frames centrais, CTA no frame final. Tipografia bold, paleta vibrante ou dark. "
        "Use quando o usuário pedir carrossel, carousel, sequência de posts ou carrossel Instagram."
    ),
    "keywords": [
        "carrossel", "carousel", "carrossel instagram", "carrossel visual",
        "sequência de posts", "sequencia de posts", "posts sequenciais",
        "carrossel de posts", "carousel instagram",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema ou assunto do carrossel",
            },
            "context_data": {
                "type": "string",
                "description": "Conteúdo, dados ou copy para os frames",
            },
            "slide_count": {
                "type": "integer",
                "description": "Número de frames/posts (padrão: 6)",
            },
        },
        "required": ["topic"],
    },
}

# ── Prompt visual ──────────────────────────────────────────────────────────────

_VISUAL_PROMPT = """\
Crie um carrossel de {slide_count} frames para Instagram sobre "{topic}" em HTML puro — visual limpo, editorial e bonito.

════════════════════════════════════════
SAÍDA OBRIGATÓRIA
════════════════════════════════════════
• Retorne APENAS o HTML completo. Comece com <!DOCTYPE html>.
• Não use markdown, blocos de código ou texto fora do HTML.

════════════════════════════════════════
ESTRUTURA HTML
════════════════════════════════════════
• Cada frame = <section class="slide">
• CSS base obrigatório:
  section.slide {{
    width: 1080px;
    height: 1080px;
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 80px;
  }}
• Frames empilhados verticalmente no documento.

════════════════════════════════════════
TIPOGRAFIA
════════════════════════════════════════
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600&display=swap');

Títulos: Playfair Display 700-900 — elegante, legível, memorável.
Corpo, kickers, indicadores: Inter — limpo e neutro.

Hierarquia obrigatória:
  • Título principal: 72-88px, Playfair Display 700, line-height 1.1
  • Subtítulo / ponto de apoio: 26-30px, Inter 400, line-height 1.6
  • Kicker / label: 13px, Inter 600, uppercase, letter-spacing 0.18em

════════════════════════════════════════
PALETA — escolha UMA conforme o tema
════════════════════════════════════════
LIGHT (padrão — leve, editorial, confiável):
  Fundo: #F8F5F1 (creme quente)
  Texto principal: #1C1917
  Texto secundário: #78716C
  Acento: escolha um tom sólido relacionado ao tema (ex: #2563EB azul, #16A34A verde, #DC2626 vermelho)
  Cards: fundo #FFFFFF, borda 1px solid #E7E2DC, border-radius 20px

DARK (quando o tema pedir autoridade ou contraste forte):
  Fundo: #111111
  Texto principal: #F5F5F4
  Texto secundário: #A8A29E
  Acento: mesma lógica acima, tom vibrante
  Cards: fundo #1C1917, borda 1px solid rgba(255,255,255,0.08), border-radius 20px

════════════════════════════════════════
IMAGENS UNSPLASH (quando disponíveis)
════════════════════════════════════════
Use como background full-bleed do frame inteiro:
  background-image: url('URL'); background-size: cover; background-position: center;
  Adicione overlay sobre a imagem:
    LIGHT: linear-gradient(to bottom, rgba(248,245,241,0.82) 0%, rgba(248,245,241,0.92) 100%)
    DARK:  linear-gradient(to bottom, rgba(17,17,17,0.65) 0%, rgba(17,17,17,0.88) 100%)
  Com overlay, o texto mantém cor da paleta escolhida com legibilidade total.
  Distribua: não repita a mesma imagem em frames consecutivos.

════════════════════════════════════════
INDICADOR DE PROGRESSO (OBRIGATÓRIO)
════════════════════════════════════════
Position absolute, top: 0, left: 0, width: 100%:
  • Trilha: height 2px, background rgba(0,0,0,0.08) [dark: rgba(255,255,255,0.08)]
  • Preenchimento: height 2px, background acento, width = (N/{slide_count} × 100)%

Indicador swipe — apenas no FRAME 1, canto inferior direito, position absolute, bottom 36px, right 44px:
  <span style="font-family:Inter;font-size:13px;font-weight:500;opacity:0.38;letter-spacing:0.05em;">
    arraste →
  </span>

════════════════════════════════════════
TIPOS DE FRAME
════════════════════════════════════════

FRAME 1 — CAPA:
  Layout centralizado, flex column, align-items center, text-align center.
  • Kicker: Inter 600, 13px, acento, uppercase, letter-spacing 0.18em, margin-bottom 20px
  • Título: Playfair Display 700, 80-96px, cor principal, line-height 1.08, máx 3 linhas
  • Subtítulo: Inter 400, 26px, cor secundária, margin-top 20px, max 2 linhas
  • Indicador "arraste →" no canto inferior direito

FRAMES CENTRAIS (2 até {last_content_frame}) — UM PONTO POR FRAME:
  Layout flex column, justify-content center, align-items flex-start (alinhado à esquerda).
  • Número do frame: Inter 600, 13px, acento, uppercase, letter-spacing 0.18em, margin-bottom 16px
    (ex: "02", "03" — com zero à esquerda)
  • Separador: div 2px × 48px, background acento, margin-bottom 24px
  • Título: Playfair Display 700, 64-72px, cor principal, line-height 1.1, máx 2 linhas
  • Corpo: Inter 400, 26px, cor secundária, line-height 1.65, max 3 linhas, margin-top 24px
  • Se houver subtópicos (máx 2): card simples com borda e border-radius 20px, padding 28px,
    Inter 500, 22px, cor secundária — sem bullets soltos, sempre dentro do card

FRAME FINAL — CTA:
  Layout centralizado.
  • Título: Playfair Display 900, 72px, cor principal, line-height 1.08, text-align center
  • Subtexto: Inter 400, 24px, cor secundária, margin-top 18px, text-align center
  • Botão visual: border-radius 12px, fundo acento, padding 20px 52px,
    Inter 600, 20px, texto branco (ou #1C1917 se fundo claro demais)
    margin-top 40px; display: inline-block

════════════════════════════════════════
CONTEÚDO / CONTEXTO BASE
════════════════════════════════════════
{context_data}

════════════════════════════════════════
INSTRUÇÃO FINAL
════════════════════════════════════════
Gere {slide_count} frames sobre "{topic}". Conteúdo educativo, direto e com valor real.
Use o contexto quando disponível; caso contrário, crie insights plausíveis e úteis.
Texto real em todos os frames — nunca placeholder.
Consistência total entre frames: mesma paleta, mesma fonte, mesmo acento.
"""

# ── Executor ──────────────────────────────────────────────────────────────────


async def execute(args: dict) -> str:
    topic = (args.get("topic") or "").strip()
    context_data = (args.get("context_data") or "").strip()
    slide_count = max(3, min(12, int(args.get("slide_count") or _DEFAULT_SLIDE_COUNT)))
    last_content_frame = slide_count - 1

    if not topic:
        return "Erro: parâmetro 'topic' é obrigatório."

    unsplash_block = await enrich_design_instruction(topic)

    model = registry.get_model("design_generator") or "anthropic/claude-3.5-sonnet"
    system_prompt = registry.get_prompt("design_generator")

    prompt = _VISUAL_PROMPT.format(
        topic=topic,
        context_data=context_data[:_MAX_CONTEXT_CHARS] if context_data else "Nenhum contexto adicional fornecido.",
        slide_count=slide_count,
        last_content_frame=last_content_frame,
    ) + unsplash_block

    try:
        data = await asyncio.wait_for(
            call_openrouter(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=6000,
                temperature=0.65,
                timeout_seconds=_TIMEOUT,
            ),
            timeout=_TIMEOUT + 5,
        )
        html = data["choices"][0]["message"]["content"].strip()
        if html.startswith("```"):
            lines = html.split("\n")
            html = "\n".join(lines[1:])
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]
            html = html.strip()
        return html
    except asyncio.TimeoutError:
        return "Erro: timeout ao gerar o carrossel visual."
    except Exception as exc:
        return f"Erro ao gerar carrossel visual: {exc}"
