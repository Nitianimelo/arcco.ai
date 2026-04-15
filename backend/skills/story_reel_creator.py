"""
Skill: story_reel_creator
Gera uma sequência de Stories/Reels para Instagram em HTML de alta qualidade visual.
Cada frame é 1080×1920px (section.slide). Retorna HTML puro como design_artifact.
"""

from __future__ import annotations

import asyncio

from backend.agents import registry
from backend.core.llm import call_openrouter
from backend.services.unsplash_service import enrich_design_instruction

# ── Configuração ──────────────────────────────────────────────────────────────

_TIMEOUT = 120.0
_DEFAULT_FRAME_COUNT = 5
_MAX_CONTEXT_CHARS = 3000

SKILL_META: dict = {
    "id": "story_reel_creator",
    "name": "Criador de Stories/Reels Instagram",
    "description": (
        "Cria uma sequência de Stories ou Reels para Instagram (1080×1920px por frame) em HTML de alta qualidade visual, "
        "pronto para preview imediato no chat. Tipografia enorme, visual full-bleed, fundo escuro ou gradiente vibrante, "
        "indicador de sequência. Máximo 3 elementos por frame para clareza em tela mobile. "
        "Use quando o usuário pedir story, stories, reels, reel ou conteúdo vertical para Instagram."
    ),
    "keywords": [
        "story", "stories", "reels", "reel", "instagram stories", "instagram reels",
        "conteúdo vertical", "conteudo vertical", "story visual", "reels visual",
        "story instagram", "reel instagram", "tela vertical",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Tema principal dos stories/reels",
            },
            "context_data": {
                "type": "string",
                "description": "Roteiro, copy ou dados de apoio",
            },
            "frame_count": {
                "type": "integer",
                "description": "Número de frames/telas (padrão: 5)",
            },
        },
        "required": ["topic"],
    },
}

# ── Prompt visual ──────────────────────────────────────────────────────────────

_VISUAL_PROMPT = """\
Crie uma sequência de {frame_count} stories/reels para Instagram sobre "{topic}" em HTML puro de alta qualidade visual.

════════════════════════════════════════
SAÍDA OBRIGATÓRIA
════════════════════════════════════════
• Retorne APENAS o HTML completo. Comece com <!DOCTYPE html>.
• Não use markdown, blocos de código ou texto fora do HTML.

════════════════════════════════════════
ESTRUTURA HTML
════════════════════════════════════════
• Cada frame = uma tag <section class="slide">
• CSS obrigatório para cada frame:
  section.slide {{
    width: 1080px;
    height: 1920px;
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 120px 60px;
  }}
• Todos os frames ficam empilhados verticalmente no documento

════════════════════════════════════════
DESIGN VISUAL — REGRAS INEGOCIÁVEIS
════════════════════════════════════════
Tipografia:
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800;900&display=swap');
  font-family: 'Inter', sans-serif;

Fundo por padrão: gradiente escuro — background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%)
Alternativa: se o tema for alegre/lifestyle, use gradiente vibrante por frame variando entre:
  linear-gradient(135deg, #4F46E5, #7C3AED)
  linear-gradient(135deg, #DB2777, #9333EA)
  linear-gradient(135deg, #0EA5E9, #6366F1)

Acento: #F97316 (laranja) ou #A855F7 (roxo) — escolha UM e mantenha.
Texto principal: #F8FAFC | Texto secundário: #CBD5E1

Máx 3 elementos por frame. Texto legível em tela mobile (mínimo 72px para headlines).
NUNCA use position:absolute para texto principal. USE flex para centralizar.
SEM animações CSS — compatível com export de imagem.

════════════════════════════════════════
INDICADOR DE SEQUÊNCIA (OBRIGATÓRIO)
════════════════════════════════════════
No topo de cada frame, adicione uma barra de progresso com dots:
• Container: display flex, gap 8px, justify-content center, margin-bottom 60px
• Cada dot: width 8px, height 8px, border-radius 50%
  - Frame atual: background #F8FAFC (branco, opacidade 1)
  - Outros frames: background rgba(248,250,252,0.3) (branco, opacidade 0.3)
• Gere {frame_count} dots, com o dot do frame atual em branco

════════════════════════════════════════
ESPECIFICAÇÃO POR FRAME
════════════════════════════════════════

FRAME 1 — ABERTURA:
• Kicker: Inter 700, 20px, acento, letras maiúsculas, tracking 0.2em
• Headline: Inter 900, 88-100px, #F8FAFC, centralizada, máx 3 linhas, text-align center
• Subtítulo: Inter 400, 36px, #CBD5E1, máx 2 linhas, text-align center

FRAMES CENTRAIS (2 até {last_frame}):
• Kicker: Inter 700, 18px, acento, letras maiúsculas, tracking 0.18em, margin-bottom 20px
• Headline do ponto: Inter 800, 72px, #F8FAFC, text-align center, max 2 linhas
• Corpo explicativo: Inter 400, 40px, #CBD5E1, text-align center, max 3 linhas

FRAME FINAL — ENCERRAMENTO:
• Mensagem principal: Inter 900, 80px, #F8FAFC, text-align center
• Subtexto: Inter 400, 36px, #CBD5E1, text-align center
• CTA visual: retângulo com border-radius 80px, padding 20px 60px,
  background acento, texto #FFFFFF, Inter 700, 28px, display inline-block

════════════════════════════════════════
CONTEÚDO / CONTEXTO BASE
════════════════════════════════════════
{context_data}

════════════════════════════════════════
INSTRUÇÃO FINAL
════════════════════════════════════════
Gere {frame_count} frames completos sobre "{topic}".
Conteúdo direto, impactante, pensado para leitura rápida em tela mobile.
Use os dados do contexto quando disponíveis; caso contrário, crie conteúdo plausível e valioso.
Cada frame deve ter texto real e específico — não use placeholder.
"""

# ── Executor ──────────────────────────────────────────────────────────────────


async def execute(args: dict) -> str:
    topic = (args.get("topic") or "").strip()
    context_data = (args.get("context_data") or "").strip()
    frame_count = max(2, min(10, int(args.get("frame_count") or _DEFAULT_FRAME_COUNT)))
    last_frame = frame_count - 1

    if not topic:
        return "Erro: parâmetro 'topic' é obrigatório."

    unsplash_block = await enrich_design_instruction(topic)

    model = registry.get_model("design_generator") or "anthropic/claude-3.5-sonnet"
    system_prompt = registry.get_prompt("design_generator")

    prompt = _VISUAL_PROMPT.format(
        topic=topic,
        context_data=context_data[:_MAX_CONTEXT_CHARS] if context_data else "Nenhum contexto adicional fornecido.",
        frame_count=frame_count,
        last_frame=last_frame,
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
        return "Erro: timeout ao gerar os stories/reels visuais."
    except Exception as exc:
        return f"Erro ao gerar stories/reels visuais: {exc}"
