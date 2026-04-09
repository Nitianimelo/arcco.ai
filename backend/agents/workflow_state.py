"""
Estados canônicos de workflows longos.

Mantém browser e análise massiva de documentos previsíveis no log e no admin.
"""

from __future__ import annotations

from typing import Mapping

from backend.agents.contracts import WorkflowStageContract


def build_mass_document_stages(
    *,
    session_items: list[dict] | None,
    awaiting_user_goal: bool,
    delivery_completed: bool = False,
) -> list[WorkflowStageContract]:
    items = session_items or []
    doc_count = len(items)
    return [
        WorkflowStageContract(
            stage_id="ingestion",
            label="Ingestion",
            status="completed" if doc_count else "pending",
            summary="Lote de documentos identificado na sessão.",
            metadata={"document_count": doc_count},
        ),
        WorkflowStageContract(
            stage_id="ocr",
            label="OCR",
            status="completed" if not awaiting_user_goal and doc_count else "pending",
            summary="Leitura/OCR preparada para os documentos do lote.",
            metadata={"document_count": doc_count},
        ),
        WorkflowStageContract(
            stage_id="rag_index",
            label="RAG Index",
            status="completed" if not awaiting_user_goal and doc_count else "pending",
            summary="Indexação temporária pronta para recuperação seletiva.",
            metadata={"ephemeral": True},
        ),
        WorkflowStageContract(
            stage_id="user_goal",
            label="User Goal",
            status="waiting_user" if awaiting_user_goal else "completed",
            summary="Objetivo do usuário para o lote documental.",
            metadata={"awaiting_goal": awaiting_user_goal},
        ),
        WorkflowStageContract(
            stage_id="retrieval",
            label="Retrieval",
            status="completed" if delivery_completed else ("pending" if awaiting_user_goal else "in_progress"),
            summary="Recuperação seletiva via RAG a partir do objetivo informado.",
            metadata={},
        ),
        WorkflowStageContract(
            stage_id="delivery",
            label="Delivery",
            status="completed" if delivery_completed else ("pending" if awaiting_user_goal else "in_progress"),
            summary="Geração da saída solicitada a partir do conteúdo recuperado.",
            metadata={},
        ),
        WorkflowStageContract(
            stage_id="cleanup",
            label="Cleanup",
            status="completed" if delivery_completed else "pending",
            summary="Descarte de artefatos temporários de OCR, chunks e índice efêmero.",
            metadata={"cleanup_policy": "ephemeral_after_delivery"},
        ),
    ]


def build_browser_workflow_stages(
    *,
    awaiting_handoff: bool,
    completed: bool = False,
    resume_token: str | None = None,
    url: str = "",
) -> list[WorkflowStageContract]:
    return [
        WorkflowStageContract(
            stage_id="open_page",
            label="Open Page",
            status="completed" if (awaiting_handoff or completed) else "in_progress",
            summary="Página carregada e inspecionada pelo navegador.",
            metadata={"url": url},
        ),
        WorkflowStageContract(
            stage_id="interactive_steps",
            label="Interactive Steps",
            status="waiting_user" if awaiting_handoff else ("completed" if completed else "in_progress"),
            summary="Execução de cliques, formulários ou interações na página.",
            metadata={"resume_token": resume_token},
        ),
        WorkflowStageContract(
            stage_id="handoff",
            label="Handoff",
            status="waiting_user" if awaiting_handoff else ("completed" if completed else "skipped"),
            summary="Intervenção humana quando houver captcha, login ou bloqueio visual.",
            metadata={"resume_token": resume_token},
        ),
        WorkflowStageContract(
            stage_id="resume",
            label="Resume",
            status="completed" if completed else ("pending" if awaiting_handoff else "in_progress"),
            summary="Retomada automática após a ação humana, quando necessária.",
            metadata={"resume_token": resume_token},
        ),
    ]


def update_workflow_stages(
    stages: list[WorkflowStageContract],
    *,
    status_by_stage: Mapping[str, str],
    metadata_by_stage: Mapping[str, dict] | None = None,
) -> list[WorkflowStageContract]:
    metadata_updates = metadata_by_stage or {}
    updated: list[WorkflowStageContract] = []
    for stage in stages:
        stage_update = {}
        if stage.stage_id in status_by_stage:
            stage_update["status"] = status_by_stage[stage.stage_id]
        if stage.stage_id in metadata_updates:
            stage_update["metadata"] = {
                **stage.metadata,
                **(metadata_updates.get(stage.stage_id) or {}),
            }
        updated.append(stage.model_copy(update=stage_update))
    return updated


def mass_document_updates_for_step_start(step_action: str) -> tuple[dict[str, str], dict[str, dict]]:
    if step_action == "session_file":
        return (
            {"ocr": "in_progress", "rag_index": "pending", "retrieval": "pending", "delivery": "pending"},
            {},
        )
    if step_action == "deep_research":
        return (
            {"ocr": "completed", "rag_index": "completed", "retrieval": "in_progress", "delivery": "pending"},
            {},
        )
    if step_action in {"text_generator", "file_modifier", "python", "design_generator"}:
        return (
            {"ocr": "completed", "rag_index": "completed", "retrieval": "completed", "delivery": "in_progress"},
            {},
        )
    return ({}, {})


def mass_document_updates_for_step_result(route: str, *, success: bool) -> tuple[dict[str, str], dict[str, dict]]:
    if route == "session_file":
        return (
            {
                "ocr": "completed" if success else "pending",
                "rag_index": "completed" if success else "pending",
            },
            {},
        )
    if route == "deep_research":
        return (
            {"retrieval": "completed" if success else "pending"},
            {},
        )
    if route in {"text_generator", "file_modifier", "python", "design_generator"}:
        return (
            {"delivery": "completed" if success else "pending"},
            {},
        )
    return ({}, {})
