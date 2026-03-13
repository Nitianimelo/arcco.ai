"""
Planner module to break down complex tasks into a deterministic JSON structure.
Uses Pydantic and OpenRouter Structured Outputs.
"""

import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

# Structured Output Schema for the Planner
class PlanStep(BaseModel):
    step: int = Field(description="Step number (1-indexed)")
    action: str = Field(description="Action type: 'web_search', 'python', 'browser', 'file_modifier', 'text_generator', 'design_generator', 'deep_research', or 'direct_answer'")
    detail: str = Field(description="A detailed description of what this step needs to accomplish.")

class PlannerOutput(BaseModel):
    is_complex: bool = Field(description="True if the request requires multiple steps or tools; False if it can be answered directly.")
    steps: List[PlanStep] = Field(description="List of steps to execute. If is_complex is False, this can be empty or have a single 'direct_answer' step.")

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

        # Let's use call_openrouter which calls OpenRouter API
        data = await call_openrouter(
            messages=messages,
            model=model,
            max_tokens=1500,
            temperature=0.1,  # Low temp for deterministic outputs
        )
        
        raw_content = data["choices"][0]["message"]["content"].strip()
        
        # Strip potential markdown backticks
        if raw_content.startswith("```"):
            raw_content = raw_content.split("\n", 1)[1]
            if raw_content.endswith("```"):
                raw_content = raw_content.rsplit("\n", 1)[0]
        
        parsed_json = json.loads(raw_content)
        return PlannerOutput.model_validate(parsed_json)
        
    except Exception as e:
        logger.error(f"[PLANNER] Falha ao gerar plano: {e}")
        # Fallback to single direct answer step on failure
        return PlannerOutput(
            is_complex=False,
            steps=[PlanStep(step=1, action="direct_answer", detail=user_intent)]
        )
