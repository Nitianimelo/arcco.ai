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


class PlannerOutputContract(BaseModel):
    is_complex: bool = Field(description="True quando a solicitacao exige fluxo multi-step.")
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


def infer_capability_id_from_action(action: str) -> str | None:
    normalized = (action or "").strip()
    if not normalized or normalized == "direct_answer":
        return None
    if normalized in _ACTION_TO_CAPABILITY_ID:
        return _ACTION_TO_CAPABILITY_ID[normalized]
    return f"skill_{normalized}"
