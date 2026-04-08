"""
Dispatcher incremental do backend.

Objetivo:
- Centralizar a resolução de tool/route/capability.
- Reduzir lógica duplicada entre planner loop e react loop.
- Permitir migração gradual sem reescrever o orquestrador inteiro.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from backend.agents.capabilities import get_capability_by_tool_name
from backend.agents.contracts import ArtifactRef, CapabilityResult
from backend.skills import loader as skills_loader


_PLANNER_ACTION_TO_TOOL = {
    "session_file": "read_session_file",
    "browser": "ask_browser",
    "web_search": "ask_web_search",
    "python": "execute_python",
    "deep_research": "deep_research",
    "file_modifier": "ask_file_modifier",
    "text_generator": "ask_text_generator",
    "design_generator": "ask_design_generator",
}

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)", re.IGNORECASE)


def planner_action_to_tool_name(action: str) -> str | None:
    if action in _PLANNER_ACTION_TO_TOOL:
        return _PLANNER_ACTION_TO_TOOL[action]
    if skills_loader.is_skill(action):
        return action
    return None


def resolve_runtime_target(func_name: str) -> dict[str, Any] | None:
    capability = get_capability_by_tool_name(func_name)
    if capability:
        return {
            "func_name": func_name,
            "route": capability["route"],
            "is_terminal": bool(capability["is_terminal"]),
            "kind": capability["kind"],
            "capability": capability,
        }

    if skills_loader.is_skill(func_name):
        return {
            "func_name": func_name,
            "route": "dynamic_skill",
            "is_terminal": False,
            "kind": "skill",
            "capability": {
                "capability_id": f"skill_{func_name}",
                "tool_name": func_name,
                "route": "dynamic_skill",
                "kind": "skill",
                "is_terminal": False,
            },
        }

    return None


def _artifact_refs_from_content(content: Any) -> list[ArtifactRef]:
    if not isinstance(content, str) or not content:
        return []
    return [
        ArtifactRef(label=label, url=url, artifact_type="file")
        for label, url in _MARKDOWN_LINK_PATTERN.findall(content)
    ]


def _capability_identity(route: str, tool_name: str) -> tuple[str, str]:
    capability = get_capability_by_tool_name(tool_name)
    if capability:
        return capability["capability_id"], capability["output_type"]
    if route == "dynamic_skill":
        return f"skill_{tool_name}", "skill_result"
    return route, "text"


def _build_dispatch_payload(
    *,
    route: str,
    tool_name: str,
    content: Any,
    message: str,
    error: bool,
    handoff: bool = False,
    handoff_payload: dict[str, Any] | None = None,
    resume_token: str | None = None,
) -> dict[str, Any]:
    capability_id, output_type = _capability_identity(route, tool_name)
    text_content = "" if content is None else str(content)
    result = CapabilityResult(
        capability_id=capability_id,
        route=route,
        status="awaiting_clarification" if handoff else ("failed" if error else "completed"),
        output_type=output_type,
        content=text_content,
        artifacts=_artifact_refs_from_content(text_content),
        handoff_required=handoff,
        error_text=text_content if error else None,
        metadata={
            "tool_name": tool_name,
            "message": message,
            "resume_token": resume_token,
            "handoff_payload": handoff_payload or {},
        },
    )
    payload = {
        "route": route,
        "tool_name": tool_name,
        "specialist_result": content,
        "message": message,
        "error": error,
        "result": result.model_dump(),
    }
    if handoff:
        payload.update(
            {
                "handoff": True,
                "handoff_payload": handoff_payload,
                "resume_token": resume_token,
            }
        )
    return payload


async def dispatch_direct_route(
    *,
    route: str,
    func_args: dict[str, Any],
    user_id: str | None,
    mode: str,
    step_label: str,
    execute_tool_fn,
    exec_with_heartbeat_fn,
    exec_browser_with_progress_fn,
    emit_file_artifacts_fn,
    browser_handoff_payload_fn,
    is_error_result_fn,
    sse_fn,
    logger,
    search_timeout: float,
    browser_timeout: float,
    skill_timeout: float,
):
    if route == "session_file":
        file_name = func_args.get("file_name", "")
        if mode == "react":
            yield sse_fn("steps", f"<step>Consultando anexo da sessão: {file_name[:60]}...</step>")
        specialist_result = await execute_tool_fn("read_session_file", func_args, user_id=user_id)
        async for artifact_event in emit_file_artifacts_fn(specialist_result):
            yield artifact_event
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name="read_session_file",
            content=specialist_result,
            message="Leitura de arquivo da sessão concluída" if mode == "planner" else "Leitura de anexo concluída",
            error=is_error_result_fn(specialist_result),
        )}
        return

    if route == "web_search":
        query = func_args.get("query", "")
        fetch_url = func_args.get("fetch_url", "")
        if mode == "react":
            yield sse_fn("steps", f"<step>Pesquisando: {query[:60]}...</step>")
        specialist_result = None
        async for event in exec_with_heartbeat_fn(
            execute_tool_fn("web_search", {"query": query}, user_id=user_id),
            lambda elapsed: sse_fn("steps", f"<step>Pesquisando na web — {int(elapsed)}s...</step>"),
            timeout=search_timeout,
        ):
            if isinstance(event, dict) and "_result" in event:
                if event.get("_timeout"):
                    specialist_result = f"Erro: Timeout de {int(search_timeout)}s na pesquisa web{' para ' + repr(query[:40]) if mode == 'react' else ''}. O serviço de busca pode estar indisponível."
                    logger.error("[DISPATCHER] web_search timeout (%s) query=%s", mode, query[:60])
                elif event.get("_error"):
                    specialist_result = f"Erro na pesquisa web: {event['_error']}"
                    logger.error("[DISPATCHER] web_search error (%s): %s", mode, event["_error"])
                else:
                    specialist_result = event["_result"]
            else:
                yield event
        if specialist_result is None:
            specialist_result = "Erro: pesquisa web não retornou resultado."

        if fetch_url and mode == "react" and not is_error_result_fn(specialist_result):
            yield sse_fn("steps", f"<step>Lendo página {fetch_url[:50]}...</step>")
            try:
                page_content = await asyncio.wait_for(
                    execute_tool_fn("web_fetch", {"url": fetch_url}, user_id=user_id),
                    timeout=20.0,
                )
                specialist_result += f"\n\n---\nConteúdo detalhado de {fetch_url}:\n{page_content}"
            except asyncio.TimeoutError:
                specialist_result += f"\n\n---\nTimeout ao ler {fetch_url}."
                logger.error("[DISPATCHER] web_fetch timeout: %s", fetch_url)
            except Exception as exc:
                specialist_result += f"\n\n---\nErro ao ler {fetch_url}: {exc}"

        async for artifact_event in emit_file_artifacts_fn(specialist_result):
            yield artifact_event
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name="web_search",
            content=specialist_result,
            message=f"Pesquisa web concluída: {query[:120]}",
            error=is_error_result_fn(specialist_result),
        )}
        return

    if route == "python":
        if mode == "react":
            yield sse_fn("steps", "<step>Executando código Python...</step>")
        else:
            yield sse_fn("steps", f"<step>Executando código Python ({step_label})...</step>")
        try:
            specialist_result = await execute_tool_fn("execute_python", func_args, user_id=user_id)
        except Exception as exc:
            logger.error("[DISPATCHER] Erro na execução Python (%s): %s", mode, exc)
            specialist_result = f"Erro ao executar Python: {exc}"
        async for artifact_event in emit_file_artifacts_fn(specialist_result):
            yield artifact_event
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name="execute_python",
            content=specialist_result,
            message="Execução Python concluída",
            error=is_error_result_fn(specialist_result),
        )}
        return

    if route == "browser":
        url = func_args.get("url", "")
        if mode == "react":
            yield sse_fn("steps", f"<step>Navegando em {url[:40]}... (modo iterativo)</step>")
        yield sse_fn("browser_action", json.dumps({
            "status": "navigating",
            "url": url,
            "title": f"Acessando {url[:60]}...",
            "actions": [a.get("type", "?") for a in func_args.get("actions", []) if isinstance(a, dict)],
        }))
        if mode == "planner":
            yield sse_fn("thought", f"Iniciando motor de navegação headless em {url}...")
            yield sse_fn("thought", "Inspecionando a página e decidindo uma ação por vez...")

        specialist_result = None
        handoff_exc = None
        async for event in exec_browser_with_progress_fn(func_args, user_id=user_id, timeout=browser_timeout):
            if isinstance(event, dict) and "_result" in event:
                if event.get("_timeout"):
                    specialist_result = f"Erro: Timeout de {int(browser_timeout)}s ao acessar {url}. O site pode estar lento ou inacessível."
                    logger.error("[DISPATCHER] Browser timeout (%s) em %s", mode, url)
                elif event.get("_error"):
                    specialist_result = f"Erro ao executar Browser Agent: {event['_error']}"
                    logger.error("[DISPATCHER] Browser error (%s): %s", mode, event["_error"])
                else:
                    specialist_result = event["_result"]
            elif isinstance(event, dict) and "_handoff" in event:
                handoff_exc = event["_handoff"]
            else:
                yield event

        if handoff_exc is not None:
            payload = browser_handoff_payload_fn(handoff_exc, url)
            yield sse_fn("browser_action", json.dumps(payload["browser_action"]))
            yield sse_fn("needs_clarification", json.dumps(payload))
            yield {"_dispatch": _build_dispatch_payload(
                route=route,
                tool_name="ask_browser",
                content="",
                message=handoff_exc.message,
                error=False,
                handoff=True,
                handoff_payload=payload,
                resume_token=handoff_exc.resume_token,
            )}
            return

        if specialist_result is None:
            specialist_result = f"Erro: browser não retornou resultado para {url}."
        async for artifact_event in emit_file_artifacts_fn(specialist_result):
            yield artifact_event
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name="ask_browser",
            content=specialist_result,
            message=f"Browser concluído para {url[:120]}",
            error=is_error_result_fn(specialist_result),
        )}
        return

    if route == "deep_research":
        from backend.agents.deep_research import run_deep_research

        research_query = func_args.get("query", "")
        research_context = func_args.get("context", "")
        if mode == "react":
            yield sse_fn("steps", f"<step>Iniciando pesquisa profunda: {research_query[:60]}...</step>")
        research_result = ""
        async for event in run_deep_research(research_query, func_args.get("_model") or "", research_context):
            if event.startswith("RESULT:"):
                research_result = event[7:]
            else:
                yield event
        if not research_result.strip():
            research_result = "A pesquisa profunda não retornou resultados. Tente reformular o pedido com mais detalhes."
        async for artifact_event in emit_file_artifacts_fn(research_result):
            yield artifact_event
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name="deep_research",
            content=research_result,
            message=f"Pesquisa profunda concluída: {research_query[:120]}",
            error=is_error_result_fn(research_result),
        )}
        return

    if route == "dynamic_skill":
        func_name = func_args.get("_func_name", "")
        skill_args = {k: v for k, v in func_args.items() if not k.startswith("_")}
        if mode == "react":
            yield sse_fn("steps", f"<step>Executando skill: {func_name}...</step>")
        else:
            yield sse_fn("steps", f"<step>Executando skill: {func_name} ({step_label})...</step>")
        specialist_result = None
        async for event in exec_with_heartbeat_fn(
            skills_loader.execute_dynamic_skill(func_name, skill_args),
            lambda elapsed: sse_fn("steps", f"<step>Executando skill {func_name} — {int(elapsed)}s...</step>"),
            timeout=skill_timeout,
        ):
            if isinstance(event, dict) and "_result" in event:
                if event.get("_timeout"):
                    specialist_result = f"Erro na skill {func_name}: Timeout de {int(skill_timeout)}s."
                    logger.error("[DISPATCHER] dynamic_skill timeout (%s) skill=%s", mode, func_name)
                elif event.get("_error"):
                    specialist_result = f"Erro na skill {func_name}: {event['_error']}"
                    logger.error("[DISPATCHER] dynamic_skill error (%s) skill=%s: %s", mode, func_name, event["_error"])
                else:
                    specialist_result = event["_result"]
            else:
                yield event
        if specialist_result is None:
            specialist_result = f"Erro na skill {func_name}: resultado vazio."
        yield {"_dispatch": _build_dispatch_payload(
            route=route,
            tool_name=func_name,
            content=specialist_result,
            message=(
                f"Skill {func_name} falhou"
                if is_error_result_fn(specialist_result)
                else f"Skill {func_name} concluída"
            ),
            error=is_error_result_fn(specialist_result),
        )}
        return
