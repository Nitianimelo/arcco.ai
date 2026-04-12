"""
Políticas centrais de decisão do workflow.

Objetivo:
- Tirar decisões de retry/continuação/clarificação do meio do orquestrador.
- Dar uma base legível para futuro harness mais robusto.
"""

from __future__ import annotations

from backend.agents.clarifier import build_follow_up_questions
from backend.agents.contracts import (
    ClarificationQuestionContract,
    PolicyDecisionContract,
    TaskTypeId,
    ValidationResultContract,
)


def _classify_browser_failure(error_text: str) -> str:
    normalized = (error_text or "").lower()
    if any(marker in normalized for marker in ("captcha", "verify you are human", "security check", "cloudflare", "acesso negado")):
        return "human_gate"
    if any(marker in normalized for marker in ("connect_over_cdp", "502 bad gateway", "websocket error", "connect.steel.dev", "steel")):
        return "infra_failure"
    if "timeout" in normalized:
        return "timeout"
    return "runtime_failure"


def decide_on_validation(
    *,
    task_type: TaskTypeId,
    route: str,
    validation_result: ValidationResultContract,
) -> PolicyDecisionContract:
    issue_codes = {issue.code for issue in validation_result.issues}
    if "missing_required_session_files" in issue_codes or "session_files_not_ready" in issue_codes:
        return PolicyDecisionContract(
            decision_id="validation_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=False,
            request_clarification=True,
            clarification_questions=validation_result.suggested_questions,
            user_message=validation_result.summary,
            metadata={
                "validator_id": validation_result.validator_id,
                "validation_status": validation_result.status,
                "enforcement": "clarification_before_file_dependent_steps",
            },
        )
    if "missing_required_user_inputs" in issue_codes:
        return PolicyDecisionContract(
            decision_id="validation_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=False,
            request_clarification=True,
            clarification_questions=validation_result.suggested_questions,
            user_message=validation_result.summary,
            metadata={
                "validator_id": validation_result.validator_id,
                "validation_status": validation_result.status,
                "enforcement": "clarification_before_next_step",
            },
        )
    if "browser_collection_recommended" in issue_codes:
        return PolicyDecisionContract(
            decision_id="validation_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=False,
            request_clarification=False,
            clarification_questions=[],
            user_message="A execução precisa de uma rota mais operacional para coletar dados com precisão.",
            metadata={
                "validator_id": validation_result.validator_id,
                "validation_status": validation_result.status,
                "suggested_replan_route": "browser",
                "enforcement": "replan_before_next_step",
            },
        )
    request_clarification = bool(validation_result.clarification_needed)
    return PolicyDecisionContract(
        decision_id="validation_policy",
        task_type=task_type,
        route=route,
        should_abort=False,
        continue_partial=True,
        request_clarification=request_clarification,
        clarification_questions=validation_result.suggested_questions,
        user_message=validation_result.summary,
        metadata={
            "validator_id": validation_result.validator_id,
            "validation_status": validation_result.status,
        },
    )


def decide_on_route_failure(
    *,
    task_type: TaskTypeId,
    route: str,
    attempt_no: int,
    error_text: str,
    is_terminal_step: bool = False,
) -> PolicyDecisionContract:
    route_retryable = route in {"web_search", "deep_research", "browser", "session_file"}
    retry_same_route = route_retryable and attempt_no == 1

    if task_type == "mass_document_analysis":
        return PolicyDecisionContract(
            decision_id="mass_document_failure_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=True,
            request_clarification=False,
            retry_same_route=retry_same_route,
            user_message="Houve uma falha parcial no pipeline documental. A execução segue com o material aproveitável.",
            metadata={"attempt_no": attempt_no, "error_text": error_text[:300]},
        )

    if task_type == "browser_workflow":
        failure_class = _classify_browser_failure(error_text)
        if route == "browser" and failure_class == "infra_failure":
            return PolicyDecisionContract(
                decision_id="browser_failure_policy",
                task_type=task_type,
                route=route,
                should_abort=False,
                continue_partial=False,
                request_clarification=False,
                retry_same_route=retry_same_route,
                clarification_questions=[],
                user_message="A infraestrutura do navegador remoto falhou. Vou tentar recuperar a coleta por uma rota auxiliar antes de resumir qualquer dado.",
                metadata={
                    "attempt_no": attempt_no,
                    "error_text": error_text[:300],
                    "failure_class": failure_class,
                },
            )
        questions = build_follow_up_questions(
            task_type=task_type,
            validation_result=ValidationResultContract(
                validator_id="browser_workflow_policy",
                task_type=task_type,
                capability_id="web_browse",
                status="clarification_recommended",
                summary="O site exigiu uma decisão de continuação.",
                issues=[],
                clarification_needed=True,
            ),
        )
        return PolicyDecisionContract(
            decision_id="browser_failure_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=False,
            request_clarification=True,
            retry_same_route=False,
            clarification_questions=questions,
            user_message="O site bloqueou parte da automação. Posso seguir parcialmente ou tentar outra abordagem.",
            metadata={
                "attempt_no": attempt_no,
                "error_text": error_text[:300],
                "failure_class": failure_class,
            },
        )

    if task_type == "spreadsheet_generation" and route == "web_search":
        questions: list[ClarificationQuestionContract] = [
            ClarificationQuestionContract(
                type="choice",
                text="A busca está incompleta. Como você quer que eu siga com a planilha?",
                options=[
                    "Entregar parcial agora",
                    "Tentar fontes mais amplas",
                    "Esperar minha confirmação",
                ],
                helper_text="A entrega parcial mantém velocidade; ampliar fontes pode incluir dados menos confiáveis.",
            )
        ]
        return PolicyDecisionContract(
            decision_id="spreadsheet_search_failure_policy",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=True,
            request_clarification=True,
            retry_same_route=retry_same_route,
            clarification_questions=questions,
            user_message="A busca falhou parcialmente. Posso continuar com cobertura parcial e sinalizar os gaps.",
            metadata={"attempt_no": attempt_no, "error_text": error_text[:300]},
        )

    # Se o step não é terminal, permitir continuação parcial com os resultados
    # acumulados até aqui. O pipeline só aborta hard em steps terminais onde
    # a entrega final depende diretamente deste resultado.
    if not is_terminal_step and not retry_same_route:
        return PolicyDecisionContract(
            decision_id="default_failure_policy_non_terminal",
            task_type=task_type,
            route=route,
            should_abort=False,
            continue_partial=True,
            request_clarification=False,
            retry_same_route=False,
            user_message=f"Falha em {route}, mas como não é o passo final, a execução segue com contexto parcial.",
            metadata={"attempt_no": attempt_no, "error_text": error_text[:300], "non_terminal_skip": True},
        )

    return PolicyDecisionContract(
        decision_id="default_failure_policy",
        task_type=task_type,
        route=route,
        should_abort=not retry_same_route,
        continue_partial=False,
        request_clarification=False,
        retry_same_route=retry_same_route,
        user_message="Falha na rota atual.",
        metadata={"attempt_no": attempt_no, "error_text": error_text[:300]},
    )
