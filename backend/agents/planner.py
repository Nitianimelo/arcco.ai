"""
Planner module to break down complex tasks into a deterministic JSON structure.
Uses Pydantic and OpenRouter Structured Outputs.
"""

import asyncio
import json
import logging
import re

from backend.core.llm import call_openrouter
from backend.agents import registry
from backend.agents.contracts import (
    ClarificationQuestionContract as ClarificationQuestion,
    PlannerOutputContract as PlannerOutput,
    PlanStepContract as PlanStep,
    infer_capability_id_from_action,
)
from backend.agents.task_types import infer_task_type

logger = logging.getLogger(__name__)

_PLANNER_TIMEOUT_SECONDS = 55.0
_PLANNER_FALLBACK_MODEL = "openai/gpt-4o-mini"

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


def _fallback_direct_answer(user_intent: str) -> PlannerOutput:
    return PlannerOutput(
        is_complex=False,
        task_type=infer_task_type(user_intent),
        acknowledgment="Ok, vou responder diretamente.",
        steps=[PlanStep(step=1, action="direct_answer", capability_id=None, detail=user_intent, is_terminal=True)],
    )


def _extract_json_payload(raw_content: str) -> dict:
    cleaned = (raw_content or "").strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    candidates = [fenced]

    match = _JSON_BLOCK_RE.search(fenced)
    if match:
        candidates.append(match.group(0))

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception as exc:
            last_error = exc

    raise ValueError(f"Planner retornou JSON invalido: {last_error}")


_ARTIFACT_TASK_TYPES: frozenset[str] = frozenset(
    {
        "design_generation",
        "document_generation",
        "deep_research",
        "mass_document_analysis",
    }
)

_DESIGN_INTENT_SIGNALS: tuple[str, ...] = (
    "slide",
    "slides",
    "apresenta",
    "deck",
    "pitch",
    "design",
    "identidade visual",
    "layout",
    "capa",
    "poster",
    "cartaz",
    "banner",
    "infogr",
    "html",
)

_DOCUMENT_INTENT_SIGNALS: tuple[str, ...] = (
    "documento",
    "relatório",
    "relatorio",
    "resumo",
    "resuma",
    "texto",
    "artigo",
    "proposta",
    "ensaio",
    "carta",
    "email",
    "briefing",
)


def _promote_terminal_direct_answer(
    steps: list[PlanStep],
    *,
    user_intent: str,
    task_type: str | None,
) -> list[PlanStep]:
    """Evita terminar o plano em direct_answer quando o pedido exige artefato.

    O supervisor tem hábito de responder diretamente com código ou markdown
    quando o step final é direct_answer, causando vazamento de tool_code no
    chat. Se detectarmos sinais de design/documento, promovemos o step final
    para a capability correta.
    """
    if not steps:
        return steps

    last = steps[-1]
    action = (last.action or "").strip()
    if action != "direct_answer":
        return steps

    normalized_intent = (user_intent or "").lower()
    normalized_task = (task_type or "").strip()

    wants_design = (
        normalized_task == "design_generation"
        or any(token in normalized_intent for token in _DESIGN_INTENT_SIGNALS)
    )
    wants_document = (
        normalized_task in {"document_generation", "deep_research", "mass_document_analysis"}
        or any(token in normalized_intent for token in _DOCUMENT_INTENT_SIGNALS)
    )

    promoted_action: str | None = None
    if wants_design:
        promoted_action = "design_generator"
    elif wants_document:
        promoted_action = "text_generator"

    if not promoted_action:
        return steps

    logger.info(
        "[PLANNER] Promovendo step final direct_answer para '%s' (task_type=%s).",
        promoted_action,
        task_type,
    )

    new_detail = last.detail or user_intent
    promoted = last.model_copy(
        update={
            "action": promoted_action,
            "capability_id": infer_capability_id_from_action(promoted_action),
            "detail": new_detail,
            "is_terminal": True,
        }
    )
    return [*steps[:-1], promoted]


def _normalize_plan(plan: PlannerOutput, *, user_intent: str) -> PlannerOutput:
    if not plan.steps:
        if plan.is_complex and not plan.needs_clarification:
            raise ValueError("Planner retornou plano complexo sem steps.")
        if plan.needs_clarification:
            return plan
        return _fallback_direct_answer(user_intent)

    normalized_steps: list[PlanStep] = []
    total_steps = len(plan.steps)
    for index, step in enumerate(plan.steps, start=1):
        action = (step.action or "").strip()
        normalized_steps.append(
            step.model_copy(
                update={
                    "step": index,
                    "action": action,
                    "capability_id": step.capability_id or infer_capability_id_from_action(action),
                    "is_terminal": step.is_terminal or (
                        index == total_steps
                        and total_steps == 1
                        and action == "direct_answer"
                    ),
                }
            )
        )

    resolved_task_type = plan.task_type or infer_task_type(user_intent, normalized_steps)

    normalized_steps = _promote_terminal_direct_answer(
        normalized_steps,
        user_intent=user_intent,
        task_type=resolved_task_type,
    )

    # Re-sequencia steps após promoção para garantir numeração coerente.
    normalized_steps = [
        step.model_copy(update={"step": idx})
        for idx, step in enumerate(normalized_steps, start=1)
    ]

    return plan.model_copy(
        update={
            "steps": normalized_steps,
            "task_type": resolved_task_type,
        }
    )


async def _request_plan(messages: list[dict], model: str, *, user_intent: str) -> PlannerOutput:
    data = await asyncio.wait_for(
        call_openrouter(
            messages=messages,
            model=model,
            max_tokens=1500,
            temperature=0.1,
        ),
        timeout=_PLANNER_TIMEOUT_SECONDS,
    )

    raw_content = data["choices"][0]["message"]["content"].strip()
    parsed_json = _extract_json_payload(raw_content)
    plan = PlannerOutput.model_validate(parsed_json)
    return _normalize_plan(plan, user_intent=user_intent)

async def generate_plan(user_intent: str, model: str) -> PlannerOutput:
    """
    Calls the LLM with structured outputs to generate a deterministic JSON plan.
    Uses the planner prompt from the registry (editable via admin).
    """
    system_prompt = registry.get_prompt("planner")

    try:
        # Pydantic schema generation
        schema = PlannerOutput.model_json_schema()
        
        # OpenRouter JSON output injection
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Pedido do usuário: {user_intent}"}
        ]
        
        # Some models on OpenRouter support `response_format` native to OpenAI SDK, we will pass it as tool or strict schema if supported.
        # But a highly reliable way is to instruct the model to respond ONLY in JSON, and provide the schema in the system prompt.
        messages[0]["content"] += f"\n\nOUTPUT SCHEMA OBRIGATÓRIO (retorne APENAS o JSON válido): {json.dumps(schema)}"

        # Injeção dinâmica de skills — filtra por relevância ao intent, evita poluir o contexto
        from backend.skills import loader as skills_loader
        _skills_desc = skills_loader.get_skill_descriptions(user_intent)
        if _skills_desc:
            messages[0]["content"] += (
                f"\n\nSKILLS DE NEGÓCIO DISPONÍVEIS (use o nome exato como valor de 'action' e capability_id como skill_<nome>):\n"
                f"{_skills_desc}"
            )

        candidate_models = [model]
        if model != _PLANNER_FALLBACK_MODEL:
            candidate_models.append(_PLANNER_FALLBACK_MODEL)

        last_error: Exception | None = None
        for candidate_model in candidate_models:
            try:
                return await _request_plan(messages, candidate_model, user_intent=user_intent)
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning(
                    "[PLANNER] Timeout de %ss no modelo '%s'.",
                    int(_PLANNER_TIMEOUT_SECONDS),
                    candidate_model,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("[PLANNER] Falha ao gerar plano com '%s': %s", candidate_model, exc)

        logger.error("[PLANNER] Fallback para resposta direta após falhas: %s", last_error)
        return _fallback_direct_answer(user_intent)

    except Exception as e:
        logger.error(f"[PLANNER] Falha ao preparar prompt do planner: {e}")
        return _fallback_direct_answer(user_intent)
