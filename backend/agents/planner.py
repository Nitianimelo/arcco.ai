"""
Planner module to break down complex tasks into a deterministic JSON structure.
Uses Pydantic and OpenRouter Structured Outputs.
"""

import asyncio
import json
import logging
import re
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

_PLANNER_TIMEOUT_SECONDS = 35.0
_PLANNER_FALLBACK_MODEL = "openai/gpt-4o-mini"

# Structured Output Schema for the Planner
class PlanStep(BaseModel):
    step: int = Field(description="Step number (1-indexed)")
    action: str = Field(description="Action type: 'web_search', 'python', 'browser', 'file_modifier', 'text_generator', 'design_generator', 'deep_research', or 'direct_answer'")
    detail: str = Field(description="A detailed description of what this step needs to accomplish.")
    is_terminal: bool = Field(
        default=False,
        description="True ONLY for the LAST step that produces the final deliverable for the user. When True, the result is sent directly to the frontend and the pipeline stops. All preceding steps MUST be False."
    )

class ClarificationQuestion(BaseModel):
    type: str = Field(description="'choice' for multiple-choice options or 'open' for free text input")
    text: str = Field(description="The question to ask the user")
    options: List[str] = Field(default_factory=list, description="Options for 'choice' type. Empty for 'open' type.")

class PlannerOutput(BaseModel):
    is_complex: bool = Field(description="True if the request requires multiple steps or tools; False if it can be answered directly.")
    steps: List[PlanStep] = Field(description="List of steps to execute. If is_complex is False, this can be empty or have a single 'direct_answer' step.")
    acknowledgment: str = Field(
        default="",
        description="Short natural phrase confirming what the agent will do. Always fill this. Ex: 'Ok, vou pesquisar barbearias na Maraponga, Fortaleza.'"
    )
    needs_clarification: bool = Field(
        default=False,
        description="True if the request is ambiguous and needs user clarification before executing. False for clear/specific requests."
    )
    questions: List[ClarificationQuestion] = Field(
        default_factory=list,
        description="Clarification questions for the user. Max 3. Only when needs_clarification is true."
    )


def _fallback_direct_answer(user_intent: str) -> PlannerOutput:
    return PlannerOutput(
        is_complex=False,
        acknowledgment="Ok, vou responder diretamente.",
        steps=[PlanStep(step=1, action="direct_answer", detail=user_intent, is_terminal=True)],
    )


async def _request_plan(messages: list[dict], model: str) -> PlannerOutput:
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
    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    if match:
        raw_content = match.group(0)

    parsed_json = json.loads(raw_content)
    plan = PlannerOutput.model_validate(parsed_json)

    if not plan.steps:
        if plan.is_complex:
            raise ValueError("Planner retornou plano complexo sem steps.")
        return _fallback_direct_answer(messages[-1]["content"])

    plan.steps = [
        step.model_copy(
            update={
                "step": index,
                "is_terminal": step.is_terminal or (
                    index == len(plan.steps)
                    and len(plan.steps) == 1
                    and step.action == "direct_answer"
                ),
            }
        )
        for index, step in enumerate(plan.steps, start=1)
    ]
    return plan

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
                f"\n\nSKILLS DE NEGÓCIO DISPONÍVEIS (use o nome exato como valor de 'action' no plano):\n"
                f"{_skills_desc}"
            )

        candidate_models = [model]
        if model != _PLANNER_FALLBACK_MODEL:
            candidate_models.append(_PLANNER_FALLBACK_MODEL)

        last_error: Exception | None = None
        for candidate_model in candidate_models:
            try:
                return await _request_plan(messages, candidate_model)
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
