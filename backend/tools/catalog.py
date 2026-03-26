"""
Catálogo Oficial de Tools — Arcco AI
======================================

Este arquivo é a FONTE DA VERDADE de todas as tools disponíveis na plataforma.

- Cada dict aqui vira um card na tela "Loja de Tools" do frontend.
- O campo `status` controla se a tool está disponível ou aparece como "Em breve".
- O campo `icon_name` é o nome do ícone Lucide usado no frontend.
- O campo `color` é a classe CSS do card no frontend (gradiente + borda).

Para adicionar uma nova tool, siga o guia em README.md desta pasta.
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# TIPO: ToolDefinition
# ─────────────────────────────────────────────────────────────────────────────

# Cada tool é um dicionário com os seguintes campos obrigatórios:
#
#  id           (str)  — identificador único, snake_case, ex: "web_search"
#  name         (str)  — nome de exibição no frontend, ex: "Busca Web"
#  description  (str)  — descrição curta (1-2 linhas) do que a tool faz
#  category     (str)  — categoria: "Pesquisa" | "Código" | "Documentos" |
#                        "Automação" | "Análise" | "Em breve"
#  status       (str)  — "available" (ativa) ou "coming_soon" (em breve)
#  icon_name    (str)  — nome do ícone Lucide React, ex: "Globe", "Code2"
#                        (consulte https://lucide.dev para a lista completa)
#  color        (str)  — classes Tailwind do card, padrão:
#                        "from-XXX-500/20 to-XXX-600/10 border-XXX-500/30"
#                        Para tools "coming_soon" use o padrão cinza abaixo.


# Padrão de cor para tools "coming_soon" (cinza neutro):
_COMING_SOON_COLOR = "from-neutral-700/20 to-neutral-800/10 border-neutral-700/30"


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────────────────────────────────────

TOOLS_CATALOG: list[dict] = [

    # ── ANÁLISE ───────────────────────────────────────────────────────────────

    {
        "id": "spy_pages",
        "name": "Spy Pages",
        "description": "Analise tráfego, engajamento, países e concorrentes de qualquer site com dados do SimilarWeb.",
        "category": "Análise",
        "status": "available",
        "icon_name": "Eye",
        "color": "from-violet-500/20 to-violet-600/10 border-violet-500/30",
    },

]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_tool_by_id(tool_id: str) -> Optional[dict]:
    """Retorna a definição de uma tool pelo seu ID, ou None se não existir."""
    return next((t for t in TOOLS_CATALOG if t["id"] == tool_id), None)


def get_available_tools() -> list[dict]:
    """Retorna apenas as tools com status 'available'."""
    return [t for t in TOOLS_CATALOG if t["status"] == "available"]
