"""
Camada operacional do open problem solver.

Objetivo:
- Dar liberdade real de composição ao agente sem perder legibilidade.
- Manter um scratchpad estável para logs, prompts e futuras IAs.
- Tornar explícito quando o sistema está resolvendo por objetivo, e não só por rota fixa.
"""

from __future__ import annotations

from typing import Any


def init_open_solver_context(
    *,
    user_intent: str,
    session_items: list[dict] | None,
    step_budget: int = 4,
) -> dict[str, Any]:
    items = session_items or []
    return {
        "objective": user_intent.strip(),
        "step_budget": step_budget,
        "steps_used": 0,
        "strategy": "Resolver o objetivo final com composição livre de capabilities, priorizando Python/E2B quando houver transformação singular de arquivos ou artefatos.",
        "session_items": [
            {
                "file_name": str(item.get("original_name") or item.get("file_name") or ""),
                "status": str(item.get("status") or ""),
            }
            for item in items
        ],
        "artifacts": [],
        "notes": [],
        "last_route": None,
        "last_status": None,
    }


def build_open_solver_prompt(*, step_detail: str, scratchpad: dict[str, Any]) -> str:
    objective = scratchpad.get("objective", "")
    strategy = scratchpad.get("strategy", "")
    step_budget = scratchpad.get("step_budget", 0)
    steps_used = scratchpad.get("steps_used", 0)
    artifacts = scratchpad.get("artifacts", [])
    notes = scratchpad.get("notes", [])
    session_items = scratchpad.get("session_items", [])

    lines = [
        "MODO OPEN PROBLEM SOLVER ATIVO.",
        f"Objetivo final: {objective}",
        f"Estratégia atual: {strategy}",
        f"Budget de iteração: {steps_used}/{step_budget} passos usados.",
        f"Passo atual: {step_detail}",
    ]

    if session_items:
        rendered_items = ", ".join(
            f"{item.get('file_name', '')} ({item.get('status', '')})"
            for item in session_items
            if item.get("file_name")
        )
        if rendered_items:
            lines.append(f"Arquivos disponíveis: {rendered_items}")

    if artifacts:
        rendered_artifacts = ", ".join(
            f"{item.get('label', 'artefato')} -> {item.get('url', '')}"
            for item in artifacts[-5:]
            if item.get("url")
        )
        if rendered_artifacts:
            lines.append(f"Artefatos já gerados: {rendered_artifacts}")

    if notes:
        lines.append("Scratchpad recente:")
        lines.extend(f"- {note}" for note in notes[-5:])

    lines.append(
        "Você tem liberdade para resolver o problema com leitura de anexos, Python/E2B, browser, design e artefatos intermediários. "
        "Prefira o caminho que realmente resolva o objetivo do usuário."
    )
    lines.append(
        "Se usar Python, é permitido criar scripts, JSON intermediário, extrair texto/imagens, montar HTML, gerar arquivos e iterar até obter o artefato final."
    )

    return "\n".join(lines)


def update_open_solver_context(
    *,
    scratchpad: dict[str, Any],
    route: str,
    success: bool,
    result_preview: str,
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    updated = dict(scratchpad or {})
    updated["steps_used"] = int(updated.get("steps_used") or 0) + 1
    updated["last_route"] = route
    updated["last_status"] = "completed" if success else "failed"

    notes = list(updated.get("notes") or [])
    status_label = "ok" if success else "erro"
    compact_preview = (result_preview or "").strip().replace("\n", " ")
    if len(compact_preview) > 220:
        compact_preview = compact_preview[:220] + "..."
    notes.append(f"{route} [{status_label}]: {compact_preview}")
    updated["notes"] = notes[-12:]

    if artifacts:
        rendered = list(updated.get("artifacts") or [])
        rendered.extend(artifacts)
        dedup: list[dict[str, Any]] = []
        seen = set()
        for item in rendered:
            key = (item.get("label"), item.get("url"))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(item)
        updated["artifacts"] = dedup[-12:]

    return updated
