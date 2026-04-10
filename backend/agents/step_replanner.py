"""
Replanejamento explícito de rota por step.

Primeiro escopo:
- rotas diretas compatíveis
- trocas simples e auditáveis
- sem reescrever o planner inteiro
"""

from __future__ import annotations

from urllib.parse import quote_plus, urlparse

from backend.agents.contracts import RouteReplanDecisionContract, TaskTypeId


_REPLAN_CANDIDATES: dict[TaskTypeId, dict[str, tuple[str, ...]]] = {
    "entity_collection": {
        "web_search": ("deep_research", "browser"),
        "browser": ("web_search",),
        "deep_research": ("web_search",),
    },
    "spreadsheet_generation": {
        "web_search": ("browser", "deep_research"),
        "deep_research": ("web_search",),
    },
    "browser_workflow": {
        "browser": ("web_search",),
        "web_search": ("browser",),
    },
    "mass_document_analysis": {
        "deep_research": ("web_search",),
    },
    "deep_research": {
        "deep_research": ("web_search",),
    },
}

_ROUTE_TO_ACTION = {
    "web_search": "web_search",
    "browser": "browser",
    "deep_research": "deep_research",
}

_ROUTE_TO_TOOL = {
    "web_search": "ask_web_search",
    "browser": "ask_browser",
    "deep_research": "deep_research",
}


def _build_query_from_context(
    *,
    failed_route: str,
    func_args: dict,
    step_detail: str,
    user_intent: str,
) -> str:
    if func_args.get("query"):
        return str(func_args["query"])
    if failed_route == "browser":
        browser_goal = str(func_args.get("goal") or "").strip()
        if browser_goal:
            return browser_goal
        url = str(func_args.get("url") or "")
        parsed = urlparse(url)
        host = parsed.netloc.replace("www.", "").strip()
        if host:
            return f"{step_detail} site:{host}"
    return step_detail or user_intent


def _infer_browser_url(*, task_type: TaskTypeId, user_intent: str, step_detail: str, func_args: dict) -> str:
    existing_url = str(func_args.get("url") or "").strip()
    if existing_url:
        return existing_url

    normalized = f"{user_intent} {step_detail}".lower()
    query = quote_plus(_build_query_from_context(
        failed_route="web_search",
        func_args=func_args,
        step_detail=step_detail,
        user_intent=user_intent,
    ))

    if any(token in normalized for token in ("passagem", "passagens", "voo", "voos", "flight", "flights")):
        return "https://www.google.com/travel/flights"
    if any(token in normalized for token in ("hotel", "hotéis", "hoteis", "hospedagem", "diária", "diarias")):
        return "https://www.google.com/travel/hotels"
    if any(token in normalized for token in ("preço", "precos", "valor", "valores", "cotação", "cotacao", "orçamento", "orcamento", "comparar")):
        return f"https://www.google.com/search?q={query}"
    return ""


def build_replanned_args(
    *,
    task_type: TaskTypeId,
    failed_route: str,
    target_route: str,
    func_args: dict,
    step_detail: str,
    user_intent: str,
) -> dict:
    if target_route in {"web_search", "deep_research"}:
        return {"query": _build_query_from_context(
            failed_route=failed_route,
            func_args=func_args,
            step_detail=step_detail,
            user_intent=user_intent,
        )}
    if target_route == "browser":
        inferred_url = _infer_browser_url(
            task_type=task_type,
            user_intent=user_intent,
            step_detail=step_detail,
            func_args=func_args,
        )
        return {
            "url": inferred_url,
            "goal": step_detail or user_intent,
        }
    return dict(func_args)


def decide_route_replan(
    *,
    task_type: TaskTypeId,
    failed_route: str,
    func_args: dict,
    step_detail: str,
    user_intent: str,
    attempted_routes: set[str],
) -> RouteReplanDecisionContract | None:
    candidates = _REPLAN_CANDIDATES.get(task_type, {}).get(failed_route, ())
    for candidate in candidates:
        if candidate in attempted_routes:
            continue
        if candidate == "browser" and not _infer_browser_url(
            task_type=task_type,
            user_intent=user_intent,
            step_detail=step_detail,
            func_args=func_args,
        ):
            continue
        return RouteReplanDecisionContract(
            decision_id="step_route_replan",
            task_type=task_type,
            from_route=failed_route,
            to_route=candidate,
            to_action=_ROUTE_TO_ACTION[candidate],
            to_tool_name=_ROUTE_TO_TOOL[candidate],
            reason="A rota original falhou e existe uma capability compatível para tentar o mesmo objetivo por outro caminho.",
            user_message=f"Rota {failed_route} falhou. Tentando {candidate} para recuperar a coleta sem inventar dados.",
            metadata={
                "attempted_routes": sorted(attempted_routes),
                "original_args": dict(func_args),
                "replanned_args": build_replanned_args(
                    task_type=task_type,
                    failed_route=failed_route,
                    target_route=candidate,
                    func_args=func_args,
                    step_detail=step_detail,
                    user_intent=user_intent,
                ),
            },
        )
    return None
