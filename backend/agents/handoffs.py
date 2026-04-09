"""
Preparação de payloads estruturados entre capabilities.

Objetivo:
- Reduzir reinterpretação em linguagem natural entre steps.
- Tornar o dado de transição audível em logs e legível por outras IAs.
"""

from __future__ import annotations

import re

from backend.agents.contracts import CapabilityResult, ReferenceEntityContract, StepHandoffContract


_SUMMARY_PATTERN = re.compile(r"\*\*Resumo:\*\*(.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL)
_SOURCE_PATTERN = re.compile(r"\[(\d+)\]\s+([^\n]+?)\s+\((https?://[^\)]+)\)", re.IGNORECASE)


def _extract_summary_entities(content: str) -> list[str]:
    summary_match = _SUMMARY_PATTERN.search(content or "")
    if not summary_match:
        return []

    summary_text = summary_match.group(1).strip()
    if ":" in summary_text:
        summary_text = summary_text.split(":", 1)[1].strip()
    summary_text = summary_text.split(". Locations", 1)[0]
    summary_text = summary_text.split(". Check", 1)[0]
    entities = [part.strip(" .") for part in re.split(r",| and ", summary_text) if part.strip()]
    return entities


def _extract_source_rows(content: str) -> list[tuple[str, str]]:
    return [(title.strip(), url.strip()) for _, title, url in _SOURCE_PATTERN.findall(content or "")]


def build_search_to_spreadsheet_handoff(
    *,
    context_results: list[CapabilityResult] | None,
) -> StepHandoffContract | None:
    search_result = next((item for item in reversed(context_results or []) if item.route == "web_search"), None)
    if not search_result:
        return None

    entity_names = _extract_summary_entities(search_result.content or "")
    source_rows = _extract_source_rows(search_result.content or "")
    reference_entities = [
        ReferenceEntityContract(
            name=name,
            source_urls=[url for _, url in source_rows[:4]],
            source_titles=[title for title, _ in source_rows[:4]],
            confidence="medium",
            notes="Entidade derivada do resumo principal da busca. Preserve o nome ao estruturar a planilha.",
        )
        for name in entity_names
    ]

    if not reference_entities:
        return None

    return StepHandoffContract(
        handoff_type="search_to_spreadsheet_reference",
        from_capability_id=search_result.capability_id,
        to_capability_id="python_execute",
        task_type="spreadsheet_generation",
        summary="Entidades principais encontradas na busca e preservadas como referência para a planilha.",
        entities=reference_entities,
        metadata={
            "search_route": search_result.route,
            "source_count": len(source_rows),
        },
    )


def build_browser_handoff_state(*, payload: dict | None, resume_token: str | None = None) -> StepHandoffContract | None:
    normalized_payload = payload or {}
    browser_action = normalized_payload.get("browser_action") or {}
    action_url = str(browser_action.get("live_url") or browser_action.get("url") or "")
    return StepHandoffContract(
        handoff_type="browser_workflow_handoff",
        from_capability_id="web_browse",
        to_capability_id="web_browse",
        task_type="browser_workflow",
        summary="Fluxo do navegador pausado aguardando intervenção humana e possível retomada.",
        entities=[],
        metadata={
            "resume_token": resume_token or normalized_payload.get("resume_token"),
            "action_url": action_url,
            "browser_action": browser_action,
            "questions": normalized_payload.get("questions", []),
        },
    )


def build_mass_document_handoff(
    *,
    session_items: list[dict] | None,
    user_intent: str,
) -> StepHandoffContract | None:
    items = session_items or []
    if not items:
        return None

    return StepHandoffContract(
        handoff_type="mass_document_context",
        from_capability_id="session_file_read",
        to_capability_id="deep_research",
        task_type="mass_document_analysis",
        summary="Lote de documentos identificado para OCR/leitura seletiva, RAG temporário e síntese guiada pelo usuário.",
        entities=[],
        metadata={
            "document_count": len(items),
            "documents": [
                {
                    "file_name": item.get("original_name") or item.get("file_name") or "",
                    "status": item.get("status") or "",
                }
                for item in items
            ],
            "user_intent": user_intent,
            "cleanup_policy": "ephemeral_after_delivery",
        },
    )
