"""
Skill: a4_document_creator
Gera um documento/apostila A4 em HTML de alta qualidade visual.
Cada página é 794×1123px (section.slide). Retorna HTML puro como design_artifact.
"""

from __future__ import annotations

import asyncio

from backend.agents import registry
from backend.core.llm import call_openrouter
from backend.services.unsplash_service import enrich_design_instruction

# ── Configuração ──────────────────────────────────────────────────────────────

_TIMEOUT = 150.0
_DEFAULT_PAGE_COUNT = 4
_MAX_CONTEXT_CHARS = 3000

SKILL_META: dict = {
    "id": "a4_document_creator",
    "name": "Criador de Documento A4",
    "description": (
        "Cria um documento ou apostila no formato A4 (794×1123px por página) em HTML de alta qualidade visual, "
        "pronto para preview imediato no chat e export em PDF. Layout profissional: header com faixa azul, "
        "hierarquia tipográfica clara, boxes de destaque, footer com numeração. "
        "Use quando o usuário pedir apostila, manual, relatório, material didático, documento A4 ou diagramação."
    ),
    "keywords": [
        "apostila", "a4", "manual", "material didático", "material didatico",
        "relatório", "relatorio", "documento a4", "diagramação", "diagramacao",
        "documento visual", "ebook", "material impresso", "guia completo",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema central do documento/apostila",
            },
            "context_data": {
                "type": "string",
                "description": "Conteúdo base, tópicos ou dados para o documento",
            },
            "page_count": {
                "type": "integer",
                "description": "Número de páginas (padrão: 4)",
            },
        },
        "required": ["topic"],
    },
}

# ── Prompt visual ──────────────────────────────────────────────────────────────

_VISUAL_PROMPT = """\
Crie um documento A4 completo de {page_count} páginas sobre "{topic}" em HTML puro de alta qualidade visual.

════════════════════════════════════════
SAÍDA OBRIGATÓRIA
════════════════════════════════════════
• Retorne APENAS o HTML completo. Comece com <!DOCTYPE html>.
• Não use markdown, blocos de código ou texto fora do HTML.

════════════════════════════════════════
ESTRUTURA HTML
════════════════════════════════════════
• Cada página = uma tag <section class="slide">
• CSS obrigatório para cada página:
  section.slide {{
    width: 794px;
    height: 1123px;
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
    background: #FFFFFF;
    display: flex;
    flex-direction: column;
  }}
• Todas as páginas ficam empilhadas verticalmente no documento

════════════════════════════════════════
DESIGN VISUAL — REGRAS INEGOCIÁVEIS
════════════════════════════════════════
Tipografia:
  @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');
  font-family: 'Source Sans 3', sans-serif;

Paleta clean/profissional:
  Fundo página: #FFFFFF
  Texto principal: #0F172A
  Texto secundário: #475569
  Acento azul: #2563EB
  Azul header: #1E40AF
  Box destaque fundo: #EFF6FF
  Box destaque borda: #2563EB
  Rodapé: #64748B

Layout: APENAS flexbox/grid. Padding interno do conteúdo: 48px lateral, 0 no topo (header já ocupa).
SEM sombras fortes — clean para export em PDF.
SEM imagens externas além das do Google Fonts.

════════════════════════════════════════
COMPONENTES OBRIGATÓRIOS EM TODAS AS PÁGINAS
════════════════════════════════════════

HEADER (todas as páginas):
  • Faixa superior: background #1E40AF, height 56px, width 100%, display flex, align-items center, padding 0 40px
  • Título do documento: Source Sans 3 600, 16px, #FFFFFF, truncado
  • Número da página: Source Sans 3 400, 14px, rgba(255,255,255,0.7), margin-left auto

FOOTER (todas as páginas):
  • Faixa inferior: background #F1F5F9, height 36px, width 100%, display flex, align-items center
  • Linha superior da faixa: 1px sólida #E2E8F0
  • Texto: "© {topic}" à esquerda + "Página N de {page_count}" à direita
  • Source Sans 3 400, 11px, #94A3B8, padding 0 40px

ÁREA DE CONTEÚDO:
  • flex: 1 (ocupa o espaço entre header e footer)
  • padding: 36px 40px
  • overflow: hidden

════════════════════════════════════════
TIPOS DE PÁGINA E ESPECIFICAÇÕES
════════════════════════════════════════

PÁGINA 1 — CAPA:
  • Header normal (título + "1 de {page_count}")
  • Área central (flex: 1): display flex, flex-direction column, justify-content center, align-items center
    - Retângulo decorativo: width 60px, height 6px, background #2563EB, margin-bottom 32px
    - Título principal: Source Sans 3 700, 44px, #0F172A, text-align center
    - Subtítulo: Source Sans 3 400, 20px, #475569, text-align center, margin-top 16px
    - Data/contexto: Source Sans 3 400, 14px, #94A3B8, margin-top 24px
  • Footer normal

PÁGINAS DE CONTEÚDO (2 até {last_content_page}):
  • Header + footer normais
  • Conteúdo da área de conteúdo:
    - Título da seção: Source Sans 3 700, 22px, #0F172A, margin-bottom 6px
    - Linha acento: width 40px, height 3px, background #2563EB, margin-bottom 20px
    - Parágrafos: Source Sans 3 400, 13px, #0F172A, line-height 1.7, margin-bottom 12px
    - Bullets: "•" em #2563EB + texto 13px #0F172A, margin-bottom 8px, padding-left 16px
    - BOX DE DESTAQUE (use 1-2 por página quando relevante):
      background #EFF6FF, border-left 4px sólida #2563EB, border-radius 4px,
      padding 16px 20px, margin 20px 0
      Texto: Source Sans 3 600, 13px, #1E40AF (título) + 400, 13px, #334155 (corpo)

ÚLTIMA PÁGINA — CONCLUSÃO:
  • Header + footer normais
  • Conteúdo:
    - Título: "Conclusão" — Source Sans 3 700, 22px, #0F172A
    - Linha acento azul: 40px × 3px
    - Resumo dos pontos principais
    - Box de destaque com mensagem final
    - Se houver referências, liste abaixo

════════════════════════════════════════
CONTEÚDO / CONTEXTO BASE
════════════════════════════════════════
{context_data}

════════════════════════════════════════
INSTRUÇÃO FINAL
════════════════════════════════════════
Gere {page_count} páginas completas sobre "{topic}".
Distribua o conteúdo de forma didática e progressiva entre as páginas.
Use os dados do contexto quando disponíveis; caso contrário, crie conteúdo educativo plausível.
Cada página deve ter texto real e relevante — não use placeholder como "Lorem ipsum".
O documento deve ter aparência profissional pronto para impressão ou envio em PDF.
"""

# ── Executor ──────────────────────────────────────────────────────────────────


async def execute(args: dict) -> str:
    topic = (args.get("topic") or "").strip()
    context_data = (args.get("context_data") or "").strip()
    page_count = max(2, min(12, int(args.get("page_count") or _DEFAULT_PAGE_COUNT)))
    last_content_page = page_count - 1

    if not topic:
        return "Erro: parâmetro 'topic' é obrigatório."

    unsplash_block = await enrich_design_instruction(topic)

    model = registry.get_model("design_generator") or "anthropic/claude-3.5-sonnet"
    system_prompt = registry.get_prompt("design_generator")

    prompt = _VISUAL_PROMPT.format(
        topic=topic,
        context_data=context_data[:_MAX_CONTEXT_CHARS] if context_data else "Nenhum contexto adicional fornecido.",
        page_count=page_count,
        last_content_page=last_content_page,
    ) + unsplash_block

    try:
        data = await asyncio.wait_for(
            call_openrouter(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=8000,
                temperature=0.55,
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
        return "Erro: timeout ao gerar o documento A4."
    except Exception as exc:
        return f"Erro ao gerar documento A4: {exc}"
