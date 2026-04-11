"""
Pré-condições explícitas da orquestração.

Objetivo:
- Centralizar checagens de intake antes do planner.
- Evitar clarificações genéricas que ignoram inventário real.
- Reduzir decisões implícitas espalhadas entre planner, prompts e orquestrador.
"""

from __future__ import annotations

from backend.agents.clarifier import build_follow_up_questions
from backend.agents.contracts import (
    ClarificationQuestionContract,
    PreconditionCheckContract,
    ValidationIssueContract,
    ValidationResultContract,
)
from backend.agents.task_types import infer_task_type, resolve_execution_engine


def _file_dependent_task(user_intent: str) -> bool:
    normalized = (user_intent or "").lower()
    file_markers = ("pdf", "arquivo", "arquivos", "anexo", "anexos", "documento", "documentos", "imagem", "imagens")
    ops = (
        "extrair",
        "reorganizar",
        "converter",
        "transformar",
        "gerar outro",
        "novo pdf",
        "crie outro design",
        "faz outro",
        "fazer outro",
        "semelhante",
        "identidade visual",
        "outra identidade",
    )
    return any(token in normalized for token in file_markers) and any(token in normalized for token in ops)


def _build_questions_for_missing_files(task_type: str) -> list[ClarificationQuestionContract]:
    validation = ValidationResultContract(
        validator_id="precondition_gate",
        task_type=task_type,
        capability_id="session_file_read",
        status="clarification_recommended",
        summary="Os anexos necessários ainda não estão disponíveis para iniciar a execução.",
        issues=[
            ValidationIssueContract(
                code="missing_required_session_files",
                severity="high",
                message="O pedido depende explicitamente de arquivos, mas nenhum anexo utilizável está pronto.",
            )
        ],
        clarification_needed=True,
    )
    return build_follow_up_questions(task_type=task_type, validation_result=validation)


def evaluate_preconditions(
    *,
    user_intent: str,
    session_items: list[dict] | None,
) -> PreconditionCheckContract:
    task_type = infer_task_type(user_intent)
    execution_engine = resolve_execution_engine(task_type)
    items = session_items or []
    ready_items = [
        item for item in items
        if str(item.get("status") or "") == "ready" and str(item.get("workspace_status") or "ready") == "ready"
    ]
    processing_items = [item for item in items if str(item.get("status") or "") in {"uploaded", "processing"}]

    if _file_dependent_task(user_intent):
        if not ready_items:
            summary = (
                "Há anexos em processamento e o fluxo depende deles."
                if processing_items
                else "O pedido depende de anexos, mas nenhum arquivo pronto foi encontrado."
            )
            return PreconditionCheckContract(
                task_type=task_type,
                execution_engine=execution_engine,
                status="clarification_required",
                summary=summary,
                blocking_reasons=["session_files_not_ready" if processing_items else "missing_required_session_files"],
                questions=_build_questions_for_missing_files(task_type),
                metadata={
                    "ready_file_count": len(ready_items),
                    "processing_file_count": len(processing_items),
                    "session_file_names": [
                        str(item.get("original_name") or item.get("file_name") or "").strip()
                        for item in items
                        if str(item.get("original_name") or item.get("file_name") or "").strip()
                    ],
                    "workspace_ready_count": len(ready_items),
                },
            )

    return PreconditionCheckContract(
        task_type=task_type,
        execution_engine=execution_engine,
        status="ok",
        summary="Pré-condições satisfeitas para iniciar a estratégia principal.",
        blocking_reasons=[],
        questions=[],
        metadata={
            "ready_file_count": len(ready_items),
            "processing_file_count": len(processing_items),
            "session_file_names": [
                str(item.get("original_name") or item.get("file_name") or "").strip()
                for item in items
                if str(item.get("original_name") or item.get("file_name") or "").strip()
            ],
            "workspace_ready_count": len(ready_items),
        },
    )
