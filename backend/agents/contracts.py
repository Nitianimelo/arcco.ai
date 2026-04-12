"""
Contratos tipados para manutenção e evolução do fluxo.

Estes modelos ainda convivem com partes legadas do runtime, mas servem
como base estável para planner, dispatcher, logs e manutenção assistida.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutionStatus = Literal[
    "planned",
    "running",
    "waiting_human",
    "waiting_job",
    "resumed",
    "completed",
    "failed",
    "awaiting_clarification",
]

TaskTypeId = Literal[
    "general_request",
    "entity_collection",
    "spreadsheet_generation",
    "document_generation",
    "design_generation",
    "file_transformation",
    "deep_research",
    "browser_workflow",
    "mass_document_analysis",
    "open_problem_solving",
]

ExecutionEngineId = Literal[
    "direct_answer",
    "structured_run",
    "open_run",
]

ValidationStatus = Literal[
    "valid",
    "valid_with_warnings",
    "insufficient_but_deliverable",
    "clarification_recommended",
]

WorkflowStageStatus = Literal[
    "pending",
    "in_progress",
    "waiting_user",
    "completed",
    "skipped",
]

PlanAction = Literal[
    "direct_answer",
    "session_file",
    "web_search",
    "python",
    "browser",
    "file_modifier",
    "text_generator",
    "design_generator",
    "deep_research",
]

_ACTION_TO_CAPABILITY_ID: dict[str, str] = {
    "session_file": "session_file_read",
    "web_search": "web_search",
    "python": "python_execute",
    "browser": "web_browse",
    "file_modifier": "file_modify",
    "text_generator": "text_document_generate",
    "design_generator": "design_generate",
    "deep_research": "deep_research",
}


class ArtifactRef(BaseModel):
    label: str = Field(description="Nome curto ou descricao do artefato")
    url: str = Field(description="URL publica do artefato")
    artifact_type: str = Field(default="generic", description="Tipo do artefato")


class ReferenceEntityContract(BaseModel):
    name: str = Field(description="Nome principal da entidade.")
    source_urls: list[str] = Field(default_factory=list, description="Fontes associadas à entidade.")
    source_titles: list[str] = Field(default_factory=list, description="Titulos curtos das fontes associadas.")
    confidence: str = Field(default="medium", description="Baixa, media ou alta, em linguagem operacional.")
    notes: str = Field(default="", description="Observações curtas que ajudam a próxima capability.")


class StepHandoffContract(BaseModel):
    handoff_type: str = Field(description="Tipo canônico do handoff entre steps.")
    from_capability_id: str = Field(description="Capability de origem.")
    to_capability_id: str = Field(description="Capability de destino.")
    task_type: TaskTypeId = Field(description="Tipo de tarefa associado ao handoff.")
    summary: str = Field(description="Resumo curto do que deve ser preservado entre os passos.")
    entities: list[ReferenceEntityContract] = Field(default_factory=list, description="Entidades estruturadas preparadas para o próximo passo.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares do handoff.")


class WorkflowStageContract(BaseModel):
    stage_id: str = Field(description="Identificador estável do estágio.")
    label: str = Field(description="Nome curto para exibição humana.")
    status: WorkflowStageStatus = Field(description="Estado atual do estágio.")
    summary: str = Field(description="Resumo operacional do estágio.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares para logs e painel.")


class PolicyDecisionContract(BaseModel):
    decision_id: str = Field(description="Identificador estável da política aplicada.")
    task_type: TaskTypeId = Field(description="Tipo de tarefa avaliado.")
    route: str = Field(description="Route avaliada.")
    should_abort: bool = Field(default=False, description="Indica se o pipeline deve ser interrompido.")
    continue_partial: bool = Field(default=False, description="Indica se a execução pode seguir parcialmente.")
    request_clarification: bool = Field(default=False, description="Indica se vale perguntar algo ao usuário.")
    retry_same_route: bool = Field(default=False, description="Indica se vale tentar a mesma route mais uma vez.")
    clarification_questions: list[ClarificationQuestionContract] = Field(default_factory=list)
    user_message: str = Field(default="", description="Mensagem curta para contexto/log/frontend.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares da decisão.")


class RouteReplanDecisionContract(BaseModel):
    decision_id: str = Field(description="Identificador estável do replanejamento.")
    task_type: TaskTypeId = Field(description="Tipo de tarefa avaliado.")
    from_route: str = Field(description="Route que falhou.")
    to_route: str = Field(description="Route alternativa escolhida.")
    to_action: str = Field(description="Action canônica correspondente à nova route.")
    to_tool_name: str = Field(description="Tool a ser chamada após o replanejamento.")
    reason: str = Field(description="Motivo objetivo do replanejamento.")
    user_message: str = Field(default="", description="Mensagem curta para trilha de execução.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares da decisão.")


class CapabilityResult(BaseModel):
    capability_id: str
    route: str
    status: ExecutionStatus
    output_type: str
    content: str = ""
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    handoff_required: bool = False
    error_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskRecord(BaseModel):
    task_id: str
    execution_id: str
    capability_id: str
    agent_id: str
    status: ExecutionStatus
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionSummary(BaseModel):
    architecture_version: str
    status: ExecutionStatus
    request_source: str
    execution_mode: Literal["normal", "agent"]
    capability_summary: dict[str, Any] = Field(default_factory=dict)
    task_summary: dict[str, Any] = Field(default_factory=dict)
    runtime_summary: dict[str, Any] = Field(default_factory=dict)


class ValidationIssueContract(BaseModel):
    code: str = Field(description="Codigo curto e estável do problema detectado.")
    severity: Literal["info", "warning", "high"] = Field(description="Severidade do achado.")
    message: str = Field(description="Descricao objetiva do achado.")
    field_name: str | None = Field(default=None, description="Campo principal afetado, quando aplicavel.")
    evidence: str | None = Field(default=None, description="Trecho curto de evidência, quando disponivel.")


class ClarificationOptionContract(BaseModel):
    label: str = Field(description="Texto curto da opcao.")
    description: str = Field(default="", description="Impacto ou explicacao curta da opcao.")
    recommended: bool = Field(default=False, description="Marca a opcao recomendada.")


class PlanStepContract(BaseModel):
    step: int = Field(description="Numero sequencial do passo, iniciando em 1.")
    action: str = Field(
        description=(
            "Acao do plano. Pode ser um dos valores canonicos do sistema "
            "ou o id exato de uma skill dinamica registrada."
        )
    )
    capability_id: str | None = Field(
        default=None,
        description=(
            "Capability canonica correspondente ao passo. "
            "Para skills dinamicas, usar skill_<nome_da_skill>."
        ),
    )
    detail: str = Field(description="Descricao operacional objetiva do passo.")
    is_terminal: bool = Field(
        default=False,
        description="True somente quando o passo encerra o pipeline e produz a entrega final.",
    )


class ClarificationQuestionContract(BaseModel):
    type: str = Field(description="'choice' para opcoes fechadas ou 'open' para texto livre.")
    text: str = Field(description="Pergunta que sera exibida ao usuario.")
    options: list[str] = Field(default_factory=list, description="Opcoes para perguntas do tipo 'choice'.")
    option_details: list[ClarificationOptionContract] = Field(
        default_factory=list,
        description="Versao estruturada das opcoes para interfaces e manutencao assistida.",
    )
    helper_text: str = Field(default="", description="Texto curto para orientar a resposta do usuario.")


class ValidationResultContract(BaseModel):
    validator_id: str = Field(description="Identificador estavel do validador executado.")
    task_type: TaskTypeId = Field(description="Tipo de tarefa avaliado.")
    capability_id: str = Field(description="Capability validada.")
    status: ValidationStatus = Field(description="Resultado resumido da validacao.")
    summary: str = Field(description="Resumo curto para logs, painel admin e contexto.")
    issues: list[ValidationIssueContract] = Field(default_factory=list, description="Achados detalhados da validacao.")
    clarification_needed: bool = Field(default=False, description="True quando vale perguntar algo ao usuario.")
    suggested_questions: list[ClarificationQuestionContract] = Field(
        default_factory=list,
        description="Perguntas sugeridas para refinamento sem ambiguidades.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares do validador.")


class PreconditionCheckContract(BaseModel):
    task_type: TaskTypeId = Field(description="Tipo de tarefa avaliado nas pré-condições.")
    execution_engine: ExecutionEngineId = Field(description="Engine operacional sugerida após intake.")
    status: Literal["ok", "clarification_required"] = Field(description="Resultado resumido das pré-condições.")
    summary: str = Field(description="Resumo curto para log, admin e frontend.")
    blocking_reasons: list[str] = Field(default_factory=list, description="Razões objetivas que impedem seguir.")
    questions: list[ClarificationQuestionContract] = Field(default_factory=list, description="Perguntas para resolver os bloqueios.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Dados auxiliares do intake.")


class PlannerOutputContract(BaseModel):
    is_complex: bool = Field(description="True quando a solicitacao exige fluxo multi-step.")
    task_type: TaskTypeId = Field(
        default="general_request",
        description="Classificacao canonica da tarefa para roteamento, validacao e logs.",
    )
    steps: list[PlanStepContract] = Field(
        default_factory=list,
        description="Plano ordenado de execucao. Pode ficar vazio quando houver clarificacao.",
    )
    acknowledgment: str = Field(
        default="",
        description="Mensagem curta de confirmacao do que sera feito.",
    )
    needs_clarification: bool = Field(
        default=False,
        description="True quando o pedido precisa de mais informacao antes da execucao.",
    )
    questions: list[ClarificationQuestionContract] = Field(
        default_factory=list,
        description="Perguntas de clarificacao para o usuario.",
    )


class ClassifierOutputContract(BaseModel):
    """Saída do classificador leve que substitui o planner."""

    task_type: TaskTypeId = Field(
        default="general_request",
        description="Classificação canônica da tarefa para roteamento e logs.",
    )
    needs_clarification: bool = Field(
        default=False,
        description="True quando o pedido precisa de mais informação antes de executar.",
    )
    clarification_questions: list[ClarificationQuestionContract] = Field(
        default_factory=list,
        description="Perguntas de clarificação para o usuário.",
    )
    hints: list[str] = Field(
        default_factory=list,
        description="Dicas operacionais para o Supervisor (ex: 'ler anexo primeiro').",
    )
    acknowledgment: str = Field(
        default="",
        description="Mensagem curta de confirmação do que será feito.",
    )


def infer_capability_id_from_action(action: str) -> str | None:
    normalized = (action or "").strip()
    if not normalized or normalized == "direct_answer":
        return None
    if normalized in _ACTION_TO_CAPABILITY_ID:
        return _ACTION_TO_CAPABILITY_ID[normalized]
    return f"skill_{normalized}"
