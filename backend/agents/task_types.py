"""
Camada canônica de tipos de tarefa.

Objetivo:
- Tornar a intenção operacional legível para humanos e IAs.
- Dar contexto estável para planner, validação, clarificação e logs.
- Evitar decisões implícitas espalhadas pelo orquestrador.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from backend.agents.contracts import ExecutionEngineId, PlanStepContract, TaskTypeId


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_intent(text: str) -> str:
    """Lowercase + remove acentos + colapsa whitespace.

    Usado apenas para detecção de keywords. Não afeta o texto original
    que vai para LLM/logs.
    """
    lowered = (text or "").lower()
    stripped = _strip_accents(lowered)
    return re.sub(r"\s+", " ", stripped)


def _has_word(haystack: str, token: str) -> bool:
    """Word-boundary match para evitar falsos positivos."""
    if not token:
        return False
    # Permite token composto (ex: "script python").
    if " " in token:
        return token in haystack
    return re.search(rf"\b{re.escape(token)}\b", haystack) is not None


@dataclass(frozen=True)
class TaskTypeDefinition:
    task_type: TaskTypeId
    execution_engine: ExecutionEngineId
    display_name: str
    description: str
    preferred_capabilities: tuple[str, ...]
    allows_partial_delivery: bool = True
    uses_text_generator: bool = False
    requires_validation: bool = True
    notes: str = ""


_TASK_TYPES: tuple[TaskTypeDefinition, ...] = (
    TaskTypeDefinition(
        task_type="general_request",
        execution_engine="direct_answer",
        display_name="Pedido Geral",
        description="Pedido sem padrão operacional específico.",
        preferred_capabilities=(),
        requires_validation=False,
    ),
    TaskTypeDefinition(
        task_type="entity_collection",
        execution_engine="structured_run",
        display_name="Coleta de Entidades",
        description="Busca e organização de empresas, pessoas, leads ou itens semelhantes.",
        preferred_capabilities=("web_search", "web_browse"),
        notes="Usa validação para evitar troca ou invenção de entidades entre passos.",
    ),
    TaskTypeDefinition(
        task_type="spreadsheet_generation",
        execution_engine="structured_run",
        display_name="Geração de Planilha",
        description="Busca, estruturação e exportação de dados tabulares.",
        preferred_capabilities=("web_search", "python_execute", "file_modify"),
        notes="Entrega parcial é permitida, mas gaps devem ser explicitados.",
    ),
    TaskTypeDefinition(
        task_type="document_generation",
        execution_engine="direct_answer",
        display_name="Geração de Documento",
        description="Produção de relatório, resumo, proposta ou documento textual.",
        preferred_capabilities=("text_document_generate", "file_modify"),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="design_generation",
        execution_engine="structured_run",
        display_name="Geração de Design",
        description="Produção de artefatos visuais ou apresentações.",
        preferred_capabilities=("design_generate",),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="file_transformation",
        execution_engine="structured_run",
        display_name="Transformação de Arquivo",
        description="Leitura, ajuste e regravação de arquivos enviados pelo usuário.",
        preferred_capabilities=("session_file_read", "file_modify"),
    ),
    TaskTypeDefinition(
        task_type="deep_research",
        execution_engine="structured_run",
        display_name="Pesquisa Profunda",
        description="Fluxo analítico de maior duração com pesquisa e síntese.",
        preferred_capabilities=("deep_research", "text_document_generate"),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="browser_workflow",
        execution_engine="structured_run",
        display_name="Fluxo de Navegador",
        description="Interação com sites, formulários, captcha e retomada com handoff humano.",
        preferred_capabilities=("web_search", "web_browse", "skill_web_form_operator"),
        notes="Quando possível, começa com descoberta de fontes e depois navegação guiada com handoff e resume token.",
    ),
    TaskTypeDefinition(
        task_type="mass_document_analysis",
        execution_engine="open_run",
        display_name="Análise Massiva de Documentos",
        description="OCR, indexação temporária, RAG seletivo e descarte posterior.",
        preferred_capabilities=("session_file_read", "deep_research", "text_document_generate"),
        uses_text_generator=True,
        notes="Fluxo pensado para OCR massivo, armazenamento temporário e cleanup no fim.",
    ),
    TaskTypeDefinition(
        task_type="open_problem_solving",
        execution_engine="open_run",
        display_name="Resolução Aberta de Problemas",
        description="Composição livre de capabilities para tarefas singulares, compostas ou pouco padronizadas.",
        preferred_capabilities=(
            "session_file_read",
            "python_execute",
            "design_generate",
            "web_browse",
            "file_modify",
            "text_document_generate",
        ),
        uses_text_generator=True,
        notes="O agente pode combinar leitura de anexos, Python, browser, design e modificação de arquivos para resolver o objetivo final.",
    ),
)


def get_task_type_catalog() -> list[dict]:
    return [asdict(item) for item in _TASK_TYPES]


def get_task_type_definition(task_type: TaskTypeId | str | None) -> dict | None:
    normalized = str(task_type or "").strip()
    for item in _TASK_TYPES:
        if item.task_type == normalized:
            return asdict(item)
    return None


def resolve_execution_engine(task_type: TaskTypeId | str | None, steps: list[PlanStepContract] | None = None) -> ExecutionEngineId:
    normalized = str(task_type or "").strip()
    definition = get_task_type_definition(normalized)
    if definition and definition.get("execution_engine"):
        return definition["execution_engine"]
    if steps:
        return "structured_run"
    return "direct_answer"


def infer_task_type(user_intent: str, steps: list[PlanStepContract] | None = None) -> TaskTypeId:
    normalized = _normalize_intent(user_intent)
    actions = {str(step.action) for step in (steps or [])}
    capability_ids = {str(step.capability_id) for step in (steps or []) if getattr(step, "capability_id", None)}

    # Sinais operacionais: composições de verbos que indicam montagem/transformação
    # livre de artefatos a partir de anexos. Usa word-boundary para não confundir
    # "texto" com "pretexto" etc.
    open_solver_signals = (
        "extrair",
        "extraia",
        "imagem",
        "imagens",
        "texto",
        "gerar",
        "gere",
        "criar",
        "crie",
        "novo pdf",
        "reorganizar",
        "reorganize",
        "recombinar",
        "converter",
        "transformar",
        "python",
        "script python",
        "html",
    )
    file_like_signals = (
        "pdf",
        "docx",
        "xlsx",
        "planilha",
        "documento",
        "documentos",
        "arquivo",
        "arquivos",
        "anexo",
        "anexos",
        "imagem",
        "imagens",
    )

    open_signal_count = sum(1 for signal in open_solver_signals if _has_word(normalized, signal))
    if open_signal_count >= 3 and any(_has_word(normalized, signal) for signal in file_like_signals):
        return "open_problem_solving"

    browser_tokens = (
        "captcha",
        "formulario",
        "formularios",
        "passagem",
        "passagens",
        "voo",
        "voos",
        "hotel",
        "hospedagem",
        "cotacao",
        "disponibilidade",
    )
    if any(_has_word(normalized, token) for token in browser_tokens):
        return "browser_workflow"
    # "preencher site" exige ambos os tokens (word-boundary em ambos).
    if _has_word(normalized, "site") and any(_has_word(normalized, tok) for tok in ("preencher", "preencha", "preenchimento")):
        return "browser_workflow"

    mass_doc_tokens = ("ocr", "rag", "lote de documentos", "muitos pdf", "varios pdf")
    if any(_has_word(normalized, token) for token in mass_doc_tokens):
        return "mass_document_analysis"

    if "deep_research" in actions or "deep_research" in capability_ids:
        return "deep_research"

    # Detecção de design_generation por keywords do intent — não depende de actions do planner.
    design_intent_tokens = (
        "design",
        "layout",
        "identidade visual",
        "visual",
        "capa",
        "banner",
        "poster",
        "cartaz",
        "flyer",
        "panfleto",
        "carrossel",
        "slide",
        "slides",
        "apresentacao",
        "pitch",
        "deck",
        "infografico",
        "landing page",
        "peca visual",
    )
    if "design_generator" in actions or "design_generate" in capability_ids or any(
        _has_word(normalized, token) for token in design_intent_tokens
    ):
        return "design_generation"

    # Detecção de document_generation por keywords do intent.
    # Tokens conservadores: só verbos/nomes que indicam "gerar texto novo",
    # não "envie o documento existente".
    document_intent_tokens = (
        "relatorio",
        "resumo",
        "resuma",
        "proposta",
        "artigo",
        "ensaio",
        "briefing",
        "redacao",
        "redigir",
        "redija",
        "escreva",
    )
    if "text_generator" in actions or "text_document_generate" in capability_ids or any(
        _has_word(normalized, token) for token in document_intent_tokens
    ):
        return "document_generation"

    if "session_file" in actions and "file_modifier" in actions:
        return "file_transformation"

    spreadsheet_tokens = ("planilha", "excel", "csv", "tabela")
    if (
        "python" in actions
        or "python_execute" in capability_ids
        or any(_has_word(normalized, token) for token in spreadsheet_tokens)
    ):
        return "spreadsheet_generation"

    entity_tokens = (
        "pesquisa",
        "pesquisar",
        "buscar",
        "busca",
        "barbearia",
        "empresa",
        "empresas",
        "contato",
        "contatos",
        "telefone",
        "endereco",
        "lead",
        "leads",
    )
    if "web_search" in actions or any(_has_word(normalized, token) for token in entity_tokens):
        return "entity_collection"

    return "general_request"
