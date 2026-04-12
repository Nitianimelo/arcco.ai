"""
Validadores incrementais do fluxo de capabilities.

Os validadores não bloqueiam entrega. Eles classificam lacunas, registram
evidências e sugerem perguntas de refinamento quando fizer sentido.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from backend.agents.clarifier import build_follow_up_questions
from backend.agents.contracts import (
    CapabilityResult,
    TaskTypeId,
    ValidationIssueContract,
    ValidationResultContract,
)


_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^\)]+)\)", re.IGNORECASE)
_PAREN_URL_PATTERN = re.compile(r"\((https?://[^\)]+)\)", re.IGNORECASE)
_RAW_URL_PATTERN = re.compile(r"https?://[^\s\)\]]+", re.IGNORECASE)
_SEARCH_SUMMARY_PATTERN = re.compile(r"\*\*Resumo:\*\*(.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL)
_BARBERSHOP_LIST_PATTERN = re.compile(r":\s*(.+)", re.DOTALL)
_TRAVEL_INTENT_PATTERN = re.compile(r"\b(passagem|passagens|voo|voos|hotel|hotéis|hoteis|diária|diarias|tarifa|tarifas|reserva|reservar)\b", re.IGNORECASE)
_PRICE_INTENT_PATTERN = re.compile(r"\b(preço|precos|valor|valores|cotação|cotacao|orçamento|orcamento|disponibilidade)\b", re.IGNORECASE)
_INTERACTIVE_COLLECTION_PATTERN = re.compile(r"\b(cotar|cotação|cotacao|simular|comparar|buscar opções|ver opções|disponibilidade|tarifa|tarifas|passagem|passagens|voo|voos|hotel|hotéis|hoteis)\b", re.IGNORECASE)
_BROAD_DESTINATION_PATTERN = re.compile(r"\b(europa|europe|américa|america|brasil|nordeste|sudeste|qualquer destino)\b", re.IGNORECASE)
_EXACT_DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b")
_MONTH_ONLY_PATTERN = re.compile(r"\b(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b", re.IGNORECASE)
_SESSION_FILE_NOT_FOUND_PATTERN = re.compile(
    r"(arquivo\s+'.+?'\s+n[aã]o encontrado na sess[aã]o|nenhum arquivo dispon[ií]vel|nenhum arquivo anexado)",
    re.IGNORECASE,
)
_SESSION_FILE_PROCESSING_PATTERN = re.compile(
    r"(ainda est[aá] em processamento|ocr/leitura ainda est[aá] rodando|n[aã]o foi poss[ií]vel ler o arquivo)",
    re.IGNORECASE,
)

# Placeholders conhecidos do fallback antigo do slide_generator — sinal de deck lixo.
_SLIDE_PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "backbone",
    "ponto 1 | ponto 2 | ponto 3",
    "ponto 1|ponto 2|ponto 3",
    "gap de dados",
    "complete com informação verificada",
    "lorem ipsum",
)
_SLIDE_COUNT_REQUEST_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"(\d{1,2})\s*slides?", re.IGNORECASE),
    re.compile(r"(\d{1,2})\s*(?:tend[eê]ncias?|tópicos?|topicos?|itens?|pontos?)", re.IGNORECASE),
)


def _infer_requested_slide_count_from_intent(user_intent: str) -> int | None:
    haystack = user_intent or ""
    for pattern in _SLIDE_COUNT_REQUEST_PATTERNS:
        match = pattern.search(haystack)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 30:
                    return value
            except ValueError:
                continue
    return None


def _normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", (value or "").lower())
    return " ".join(normalized.split())


def _extract_source_urls(content: str) -> list[str]:
    urls: list[str] = []
    for pattern in (_LINK_PATTERN, _PAREN_URL_PATTERN, _RAW_URL_PATTERN):
        urls.extend(pattern.findall(content or ""))
    seen: set[str] = set()
    normalized_urls: list[str] = []
    for url in urls:
        clean = str(url).rstrip(").,")
        if clean in seen:
            continue
        seen.add(clean)
        normalized_urls.append(clean)
    return normalized_urls


def _looks_like_interactive_collection(user_intent: str) -> bool:
    normalized = user_intent or ""
    return bool(_INTERACTIVE_COLLECTION_PATTERN.search(normalized) and _PRICE_INTENT_PATTERN.search(normalized))


def _has_travel_scope_gaps(user_intent: str) -> bool:
    normalized = user_intent or ""
    if not _TRAVEL_INTENT_PATTERN.search(normalized):
        return False
    broad_destination = bool(_BROAD_DESTINATION_PATTERN.search(normalized))
    has_exact_date = bool(_EXACT_DATE_PATTERN.search(normalized))
    month_only = bool(_MONTH_ONLY_PATTERN.search(normalized))
    return broad_destination or (month_only and not has_exact_date)


def _parse_search_entities(content: str) -> list[str]:
    if not content:
        return []

    summary_match = _SEARCH_SUMMARY_PATTERN.search(content)
    if not summary_match:
        return []
    summary_text = summary_match.group(1).strip()
    names_match = _BARBERSHOP_LIST_PATTERN.search(summary_text)
    if not names_match:
        return []

    names_block = names_match.group(1)
    names_block = names_block.split(". Locations", 1)[0]
    names_block = names_block.split(". Check", 1)[0]
    parts = [part.strip(" .") for part in re.split(r",| and ", names_block) if part.strip()]
    return parts


def extract_reference_entities(context_results: list[CapabilityResult] | None) -> list[str]:
    prior_search = next((item for item in reversed(context_results or []) if item.route == "web_search"), None)
    if not prior_search:
        return []
    return _parse_search_entities(prior_search.content or "")


def _parse_python_named_list(code: str) -> list[str]:
    if not code:
        return []

    list_match = re.search(
        r"\"Nome da Barbearia\"\s*:\s*(\[[\s\S]*?\])",
        code,
        re.IGNORECASE,
    )
    if not list_match:
        return []

    try:
        values = ast.literal_eval(list_match.group(1))
    except Exception:
        return []

    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def validate_capability_execution(
    *,
    task_type: TaskTypeId,
    route: str,
    capability_result: CapabilityResult,
    input_payload: dict[str, Any] | None = None,
    context_results: list[CapabilityResult] | None = None,
    user_intent: str | None = None,
) -> ValidationResultContract | None:
    if route == "web_search" and task_type in {"entity_collection", "spreadsheet_generation", "browser_workflow"}:
        urls = _extract_source_urls(capability_result.content or "")
        status = "valid" if len(urls) >= 4 else "valid_with_warnings"
        issues: list[ValidationIssueContract] = []
        if len(urls) < 4:
            issues.append(
                ValidationIssueContract(
                    code="limited_source_coverage",
                    severity="warning",
                    message=f"A busca retornou apenas {len(urls)} fonte(s) identificáveis no resumo bruto.",
                    field_name="sources",
                )
            )
        if _has_travel_scope_gaps(user_intent or ""):
            issues.append(
                ValidationIssueContract(
                    code="missing_required_user_inputs",
                    severity="high",
                    message="O pedido ainda não define destino específico ou datas exatas o bastante para uma coleta comparativa confiável.",
                    field_name="scope",
                )
            )
            status = "clarification_recommended"
        elif _looks_like_interactive_collection(user_intent or ""):
            issues.append(
                ValidationIssueContract(
                    code="browser_collection_recommended",
                    severity="warning",
                    message="A tarefa parece exigir filtros e interação em sites, não apenas busca textual.",
                    field_name="route",
                )
            )
            status = "clarification_recommended" if status == "valid" else "insufficient_but_deliverable"
        result = ValidationResultContract(
            validator_id="search_result_quality",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status=status,
            summary=(
                "Busca coletada com cobertura suficiente."
                if status == "valid"
                else "Busca coletada, mas precisa de mais precisão antes do entregável final."
                if status == "clarification_recommended"
                else "Busca coletada, mas com cobertura parcial."
            ),
            issues=issues,
            clarification_needed=status == "clarification_recommended",
            metadata={"source_count": len(urls)},
        )
        if result.clarification_needed:
            result.suggested_questions = build_follow_up_questions(task_type=task_type, validation_result=result)
        return result

    if route == "python" and task_type == "spreadsheet_generation":
        prior_search = next((item for item in reversed(context_results or []) if item.route == "web_search"), None)
        if not prior_search:
            return None

        search_entities = _parse_search_entities(prior_search.content or "")
        python_entities = _parse_python_named_list((input_payload or {}).get("code", ""))
        search_norm = {_normalize_name(name): name for name in search_entities}
        python_norm = {_normalize_name(name): name for name in python_entities}
        overlap = sorted(set(search_norm).intersection(python_norm))

        if not search_entities or not python_entities:
            issues = [
                ValidationIssueContract(
                    code="unstructured_step_payload",
                    severity="warning",
                    message="Não foi possível comparar os itens buscados com os itens enviados para o Python.",
                )
            ]
            result = ValidationResultContract(
                validator_id="search_to_python_consistency",
                task_type=task_type,
                capability_id=capability_result.capability_id,
                status="valid_with_warnings",
                summary="Planilha gerada sem trilha estruturada suficiente para conferência completa.",
                issues=issues,
                clarification_needed=False,
                metadata={
                    "search_entities": search_entities,
                    "python_entities": python_entities,
                },
            )
            return result

        if overlap and len(overlap) == len(python_norm):
            return ValidationResultContract(
                validator_id="search_to_python_consistency",
                task_type=task_type,
                capability_id=capability_result.capability_id,
                status="valid",
                summary="A planilha usou os mesmos itens principais encontrados na busca.",
                issues=[],
                clarification_needed=False,
                metadata={
                    "search_entities": search_entities,
                    "python_entities": python_entities,
                    "overlap_count": len(overlap),
                },
            )

        overlap_names = [search_norm[name] for name in overlap if name in search_norm]
        issues = [
            ValidationIssueContract(
                code="search_to_python_entity_mismatch",
                severity="high",
                message="Os itens enviados para a planilha não batem integralmente com os itens principais retornados pela busca.",
                field_name="entities",
                evidence=(
                    f"Busca: {', '.join(search_entities[:4]) or '—'} | "
                    f"Planilha: {', '.join(python_entities[:4]) or '—'}"
                ),
            )
        ]
        result = ValidationResultContract(
            validator_id="search_to_python_consistency",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status="insufficient_but_deliverable",
            summary="A planilha foi entregue, mas há divergência entre o resultado da busca e os itens estruturados.",
            issues=issues,
            clarification_needed=True,
            metadata={
                "search_entities": search_entities,
                "python_entities": python_entities,
                "overlap_entities": overlap_names,
                "overlap_count": len(overlap_names),
            },
        )
        result.suggested_questions = build_follow_up_questions(task_type=task_type, validation_result=result)
        return result

    if route == "browser" and capability_result.handoff_required:
        result = ValidationResultContract(
            validator_id="browser_handoff_state",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status="clarification_recommended",
            summary="O navegador encontrou um bloqueio que exige ação humana para retomar.",
            issues=[
                ValidationIssueContract(
                    code="browser_handoff_required",
                    severity="high",
                    message="Captcha, login ou bloqueio visual detectado durante o fluxo do navegador.",
                )
            ],
            clarification_needed=True,
            metadata=capability_result.metadata,
        )
        result.suggested_questions = build_follow_up_questions(task_type=task_type, validation_result=result)
        return result

    if route == "browser" and capability_result.error_text:
        error_text = str(capability_result.error_text or "")
        lower_error = error_text.lower()
        failure_code = "browser_runtime_failure"
        failure_summary = "O navegador falhou durante a execução."
        clarification_needed = False

        if any(marker in lower_error for marker in ("captcha", "verify you are human", "security check", "cloudflare")):
            failure_code = "browser_handoff_required"
            failure_summary = "O navegador encontrou um bloqueio visual e precisa de ação humana."
            clarification_needed = True
        elif any(marker in lower_error for marker in ("steel", "connect_over_cdp", "502 bad gateway", "websocket error", "connect.steel.dev")):
            failure_code = "browser_infra_failure"
            failure_summary = "A infraestrutura remota do navegador falhou antes de concluir a coleta."

        result = ValidationResultContract(
            validator_id="browser_failure_classification",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status="clarification_recommended" if clarification_needed else "valid_with_warnings",
            summary=failure_summary,
            issues=[
                ValidationIssueContract(
                    code=failure_code,
                    severity="high" if clarification_needed else "warning",
                    message=error_text[:300] or failure_summary,
                )
            ],
            clarification_needed=clarification_needed,
            metadata={
                **capability_result.metadata,
                "failure_class": failure_code,
            },
        )
        if clarification_needed:
            result.suggested_questions = build_follow_up_questions(task_type=task_type, validation_result=result)
        return result

    if route == "session_file" and task_type in {"open_problem_solving", "mass_document_analysis", "file_transformation"}:
        content = str(capability_result.content or capability_result.error_text or "")
        issues: list[ValidationIssueContract] = []
        status = "valid"

        if _SESSION_FILE_NOT_FOUND_PATTERN.search(content):
            issues.append(
                ValidationIssueContract(
                    code="missing_required_session_files",
                    severity="high",
                    message="O fluxo depende de anexos da sessão, mas os arquivos citados não estão disponíveis.",
                    field_name="session_files",
                    evidence=content[:220] or None,
                )
            )
            status = "clarification_recommended"
        elif _SESSION_FILE_PROCESSING_PATTERN.search(content):
            issues.append(
                ValidationIssueContract(
                    code="session_files_not_ready",
                    severity="warning",
                    message="Os anexos existem, mas ainda não estão prontos para leitura confiável.",
                    field_name="session_files",
                    evidence=content[:220] or None,
                )
            )
            status = "clarification_recommended"

        if issues:
            result = ValidationResultContract(
                validator_id="session_file_readiness",
                task_type=task_type,
                capability_id=capability_result.capability_id,
                status=status,
                summary=(
                    "Os anexos necessários ainda não estão disponíveis para o solver."
                    if status == "clarification_recommended"
                    else "Leitura de anexos concluída."
                ),
                issues=issues,
                clarification_needed=status == "clarification_recommended",
                metadata={"content_preview": content[:300]},
            )
            if result.clarification_needed:
                result.suggested_questions = build_follow_up_questions(task_type=task_type, validation_result=result)
            return result

    # ── Validação de qualidade de design (route: design_generator) ──────────
    if route == "design_generator":
        raw = str(capability_result.content or "")
        issues: list[ValidationIssueContract] = []
        stripped = raw.strip()

        if not stripped:
            issues.append(
                ValidationIssueContract(
                    code="design_empty_output",
                    severity="high",
                    message="O design_generator retornou conteúdo vazio.",
                    field_name="content",
                )
            )
        else:
            lowered = stripped.lower()
            # Detecta vazamento de tool_code como texto no HTML gerado.
            if any(marker in lowered for marker in ("<tool_code", "```tool_code", "ask_design_generator(", "ask_text_generator(")):
                issues.append(
                    ValidationIssueContract(
                        code="design_tool_code_leak",
                        severity="high",
                        message="O output do design_generator contém vazamento de tool_code em vez de HTML.",
                        field_name="content",
                    )
                )
            # Verifica presença mínima de estrutura HTML/CSS.
            has_html_tag = "<div" in lowered or "<section" in lowered or "<html" in lowered
            if not has_html_tag:
                issues.append(
                    ValidationIssueContract(
                        code="design_missing_html_structure",
                        severity="high",
                        message="O conteúdo retornado não contém elementos HTML estruturais esperados.",
                        field_name="content",
                    )
                )
            # Contagem de slides para apresentações vs solicitado.
            slide_hits = len(re.findall(r'<div[^>]+class=["\'][^"\']*\bslide\b', stripped, re.IGNORECASE))
            requested_count = _infer_requested_slide_count_from_intent(user_intent or "")
            if requested_count and slide_hits and slide_hits < requested_count:
                issues.append(
                    ValidationIssueContract(
                        code="design_slide_count_below_request",
                        severity="high",
                        message=(
                            f"O usuário pediu {requested_count} slides, mas o design final veio com {slide_hits}."
                        ),
                        field_name="slides",
                    )
                )

        if not issues:
            return ValidationResultContract(
                validator_id="design_generator_quality",
                task_type=task_type,
                capability_id=capability_result.capability_id,
                status="valid",
                summary="Design gerado com estrutura HTML válida.",
                issues=[],
                clarification_needed=False,
                metadata={"content_length": len(stripped)},
            )

        high_severity = any(issue.severity == "high" for issue in issues)
        return ValidationResultContract(
            validator_id="design_generator_quality",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status="insufficient_but_deliverable" if high_severity else "valid_with_warnings",
            summary="Design gerado, porém com problemas de qualidade.",
            issues=issues,
            clarification_needed=False,
            metadata={"content_length": len(stripped)},
        )

    # ── Validação de qualidade de slide deck (skill: slide_generator) ────────
    capability_id = str(capability_result.capability_id or "")
    if capability_id == "skill_slide_generator" or (
        route == "dynamic_skill" and "slide_generator" in capability_id
    ):
        raw_content = str(capability_result.content or "")
        deck: dict[str, Any] | None = None
        try:
            deck = json.loads(raw_content) if raw_content.strip().startswith("{") else None
        except Exception:
            deck = None

        issues: list[ValidationIssueContract] = []
        slide_list: list[dict[str, Any]] = []
        if isinstance(deck, dict):
            slide_list = deck.get("slides") or []

        slide_count = len(slide_list)
        requested_count = _infer_requested_slide_count_from_intent(user_intent or "")

        if requested_count and slide_count < requested_count:
            issues.append(
                ValidationIssueContract(
                    code="slide_count_below_request",
                    severity="high",
                    message=(
                        f"O usuário pediu {requested_count} slides/itens, mas o deck veio com {slide_count}."
                    ),
                    field_name="slides",
                )
            )

        lowered_content = raw_content.lower()
        placeholder_hits = [marker for marker in _SLIDE_PLACEHOLDER_MARKERS if marker in lowered_content]
        if placeholder_hits:
            issues.append(
                ValidationIssueContract(
                    code="slide_deck_placeholder_content",
                    severity="high",
                    message=(
                        "O deck contém placeholders genéricos (ex.: "
                        + ", ".join(placeholder_hits[:3])
                        + "). Isso indica que o LLM falhou e o fallback entregou conteúdo sem substância."
                    ),
                    field_name="slides",
                )
            )

        empty_bullet_slides = 0
        for slide in slide_list:
            if not isinstance(slide, dict):
                continue
            if slide.get("layout") == "bullets":
                pts = slide.get("points") or []
                if not pts or all(not str(p).strip() for p in pts):
                    empty_bullet_slides += 1
        if empty_bullet_slides > 0:
            issues.append(
                ValidationIssueContract(
                    code="slide_empty_bullets",
                    severity="warning",
                    message=f"{empty_bullet_slides} slide(s) com layout 'bullets' sem pontos de conteúdo.",
                    field_name="slides",
                )
            )

        if not slide_list:
            issues.append(
                ValidationIssueContract(
                    code="slide_deck_empty",
                    severity="high",
                    message="O deck foi retornado sem slides utilizáveis.",
                    field_name="slides",
                )
            )

        if not issues:
            return ValidationResultContract(
                validator_id="slide_deck_quality",
                task_type=task_type,
                capability_id=capability_result.capability_id,
                status="valid",
                summary=f"Deck com {slide_count} slides validado.",
                issues=[],
                clarification_needed=False,
                metadata={"slide_count": slide_count, "requested_count": requested_count},
            )

        high_severity = any(issue.severity == "high" for issue in issues)
        status_value = "insufficient_but_deliverable" if high_severity else "valid_with_warnings"
        return ValidationResultContract(
            validator_id="slide_deck_quality",
            task_type=task_type,
            capability_id=capability_result.capability_id,
            status=status_value,
            summary=(
                f"Deck entregue com {slide_count} slides, mas com problemas que afetam a qualidade."
            ),
            issues=issues,
            clarification_needed=False,
            metadata={
                "slide_count": slide_count,
                "requested_count": requested_count,
                "placeholder_hits": placeholder_hits,
                "empty_bullet_slides": empty_bullet_slides,
            },
        )

    return None
