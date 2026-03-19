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

    # ── PESQUISA ──────────────────────────────────────────────────────────────

    {
        "id": "web_search",
        "name": "Busca Web",
        "description": "Pesquisa informações atualizadas na internet usando múltiplas fontes via Tavily.",
        "category": "Pesquisa",
        "status": "available",
        "icon_name": "Globe",
        "color": "from-blue-500/20 to-blue-600/10 border-blue-500/30",
    },
    {
        "id": "deep_research",
        "name": "Pesquisa Profunda",
        "description": "Realiza pesquisa aprofundada com análise de múltiplas fontes e síntese inteligente.",
        "category": "Pesquisa",
        "status": "available",
        "icon_name": "SearchCode",
        "color": "from-indigo-500/20 to-indigo-600/10 border-indigo-500/30",
    },

    # ── AUTOMAÇÃO ─────────────────────────────────────────────────────────────

    {
        "id": "browser",
        "name": "Navegador Inteligente",
        "description": "Controla um navegador headless para automatizar tarefas, coletar dados e interagir com sites.",
        "category": "Automação",
        "status": "available",
        "icon_name": "Monitor",
        "color": "from-purple-500/20 to-purple-600/10 border-purple-500/30",
    },

    # ── CÓDIGO ────────────────────────────────────────────────────────────────

    {
        "id": "python_executor",
        "name": "Execução Python",
        "description": "Executa código Python em sandbox seguro na nuvem via E2B. Ideal para cálculos e automações.",
        "category": "Código",
        "status": "available",
        "icon_name": "Code2",
        "color": "from-yellow-500/20 to-yellow-600/10 border-yellow-500/30",
    },

    # ── DOCUMENTOS ────────────────────────────────────────────────────────────

    {
        "id": "doc_generator",
        "name": "Gerador de Documentos",
        "description": "Cria documentos profissionais em DOCX e PDF com formatação automática.",
        "category": "Documentos",
        "status": "available",
        "icon_name": "FileText",
        "color": "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30",
    },
    {
        "id": "presentation_generator",
        "name": "Apresentações",
        "description": "Gera apresentações visuais em HTML com design profissional e exportação PPTX.",
        "category": "Documentos",
        "status": "available",
        "icon_name": "Presentation",
        "color": "from-orange-500/20 to-orange-600/10 border-orange-500/30",
    },
    {
        "id": "spreadsheet_tool",
        "name": "Planilhas Excel",
        "description": "Cria e manipula planilhas Excel com fórmulas, gráficos e formatação condicional.",
        "category": "Documentos",
        "status": "available",
        "icon_name": "Table2",
        "color": "from-green-500/20 to-green-600/10 border-green-500/30",
    },
    {
        "id": "ocr",
        "name": "OCR — Leitura de Imagens",
        "description": "Extrai texto de imagens, fotos de documentos e capturas de tela com alta precisão.",
        "category": "Documentos",
        "status": "available",
        "icon_name": "Eye",
        "color": "from-teal-500/20 to-teal-600/10 border-teal-500/30",
    },

    # ── ANÁLISE ───────────────────────────────────────────────────────────────

    {
        "id": "file_analysis",
        "name": "Análise de Arquivos",
        "description": "Analisa PDFs, planilhas e CSVs para extrair insights e responder perguntas sobre o conteúdo.",
        "category": "Análise",
        "status": "available",
        "icon_name": "BarChart3",
        "color": "from-cyan-500/20 to-cyan-600/10 border-cyan-500/30",
    },
    {
        "id": "data_visualization",
        "name": "Visualização de Dados",
        "description": "Gera gráficos e dashboards interativos a partir dos seus dados.",
        "category": "Análise",
        "status": "coming_soon",
        "icon_name": "BarChart3",
        "color": _COMING_SOON_COLOR,
    },

    # ── EM BREVE ──────────────────────────────────────────────────────────────

    {
        "id": "image_generator",
        "name": "Gerador de Imagens",
        "description": "Cria imagens e ilustrações via IA usando DALL-E ou Stable Diffusion.",
        "category": "Em breve",
        "status": "coming_soon",
        "icon_name": "Image",
        "color": _COMING_SOON_COLOR,
    },
    {
        "id": "email_sender",
        "name": "Envio de E-mail",
        "description": "Automatiza o envio de e-mails e respostas via Gmail ou SMTP configurável.",
        "category": "Em breve",
        "status": "coming_soon",
        "icon_name": "Mail",
        "color": _COMING_SOON_COLOR,
    },
    {
        "id": "crm_integration",
        "name": "Integração CRM",
        "description": "Conecta com Salesforce, HubSpot e Pipedrive para atualizar negócios automaticamente.",
        "category": "Em breve",
        "status": "coming_soon",
        "icon_name": "Database",
        "color": _COMING_SOON_COLOR,
    },
    {
        "id": "webhook_automation",
        "name": "Automação Webhook",
        "description": "Dispara webhooks e integra com n8n, Make, Zapier e outros serviços no-code.",
        "category": "Em breve",
        "status": "coming_soon",
        "icon_name": "Zap",
        "color": _COMING_SOON_COLOR,
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
