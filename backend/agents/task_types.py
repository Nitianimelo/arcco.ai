"""
Camada canônica de tipos de tarefa.

Objetivo:
- Tornar a intenção operacional legível para humanos e IAs.
- Dar contexto estável para planner, validação, clarificação e logs.
- Evitar decisões implícitas espalhadas pelo orquestrador.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.agents.contracts import PlanStepContract, TaskTypeId


@dataclass(frozen=True)
class TaskTypeDefinition:
    task_type: TaskTypeId
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
        display_name="Pedido Geral",
        description="Pedido sem padrão operacional específico.",
        preferred_capabilities=(),
        requires_validation=False,
    ),
    TaskTypeDefinition(
        task_type="entity_collection",
        display_name="Coleta de Entidades",
        description="Busca e organização de empresas, pessoas, leads ou itens semelhantes.",
        preferred_capabilities=("web_search", "web_browse"),
        notes="Usa validação para evitar troca ou invenção de entidades entre passos.",
    ),
    TaskTypeDefinition(
        task_type="spreadsheet_generation",
        display_name="Geração de Planilha",
        description="Busca, estruturação e exportação de dados tabulares.",
        preferred_capabilities=("web_search", "python_execute", "file_modify"),
        notes="Entrega parcial é permitida, mas gaps devem ser explicitados.",
    ),
    TaskTypeDefinition(
        task_type="document_generation",
        display_name="Geração de Documento",
        description="Produção de relatório, resumo, proposta ou documento textual.",
        preferred_capabilities=("text_document_generate", "file_modify"),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="design_generation",
        display_name="Geração de Design",
        description="Produção de artefatos visuais ou apresentações.",
        preferred_capabilities=("design_generate",),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="file_transformation",
        display_name="Transformação de Arquivo",
        description="Leitura, ajuste e regravação de arquivos enviados pelo usuário.",
        preferred_capabilities=("session_file_read", "file_modify"),
    ),
    TaskTypeDefinition(
        task_type="deep_research",
        display_name="Pesquisa Profunda",
        description="Fluxo analítico de maior duração com pesquisa e síntese.",
        preferred_capabilities=("deep_research", "text_document_generate"),
        uses_text_generator=True,
    ),
    TaskTypeDefinition(
        task_type="browser_workflow",
        display_name="Fluxo de Navegador",
        description="Interação com sites, formulários, captcha e retomada com handoff humano.",
        preferred_capabilities=("web_search", "web_browse", "skill_web_form_operator"),
        notes="Quando possível, começa com descoberta de fontes e depois navegação guiada com handoff e resume token.",
    ),
    TaskTypeDefinition(
        task_type="mass_document_analysis",
        display_name="Análise Massiva de Documentos",
        description="OCR, indexação temporária, RAG seletivo e descarte posterior.",
        preferred_capabilities=("session_file_read", "deep_research", "text_document_generate"),
        uses_text_generator=True,
        notes="Fluxo pensado para OCR massivo, armazenamento temporário e cleanup no fim.",
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


def infer_task_type(user_intent: str, steps: list[PlanStepContract] | None = None) -> TaskTypeId:
    normalized = (user_intent or "").lower()
    actions = {str(step.action) for step in (steps or [])}
    capability_ids = {str(step.capability_id) for step in (steps or []) if getattr(step, "capability_id", None)}

    if (
        "captcha" in normalized
        or "formul" in normalized
        or "site" in normalized and "preench" in normalized
        or any(token in normalized for token in ("passagem", "passagens", "voo", "voos", "hotel", "hospedagem", "cotação", "cotacao", "disponibilidade"))
    ):
        return "browser_workflow"
    if any(token in normalized for token in ("ocr", "rag", "lote de documentos", "muitos pdf", "vários pdf", "varios pdf")):
        return "mass_document_analysis"
    if "deep_research" in actions or "deep_research" in capability_ids:
        return "deep_research"
    if "design_generator" in actions or "design_generate" in capability_ids:
        return "design_generation"
    if "text_generator" in actions or "text_document_generate" in capability_ids:
        return "document_generation"
    if "session_file" in actions and "file_modifier" in actions:
        return "file_transformation"
    if "python" in actions or "python_execute" in capability_ids or any(token in normalized for token in ("planilha", "excel", "csv", "tabela")):
        return "spreadsheet_generation"
    if "web_search" in actions or any(
        token in normalized
        for token in ("pesquisa", "buscar", "barbearia", "empresa", "contato", "telefone", "endereço", "endereco", "lead")
    ):
        return "entity_collection"
    return "general_request"
