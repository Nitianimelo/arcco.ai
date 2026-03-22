import logging
from typing import Any

from backend.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_TABLE_NAME = "agent_model_overrides"


def list_agent_model_overrides() -> dict[str, str]:
    try:
        rows = get_supabase_client().query(
            _TABLE_NAME,
            "agent_id,model",
            None,
            "agent_id.asc",
            200,
        )
    except Exception as exc:
        logger.warning("[AGENT_MODELS] Failed to list overrides from Supabase: %s", exc)
        return {}

    overrides: dict[str, str] = {}
    for row in rows or []:
        agent_id = str(row.get("agent_id") or "").strip()
        model = str(row.get("model") or "").strip()
        if agent_id and model:
            overrides[agent_id] = model
    return overrides


def save_agent_model_override(agent_id: str, model: str) -> dict[str, Any] | None:
    payload = {
        "agent_id": agent_id,
        "model": model,
    }
    try:
        return get_supabase_client().upsert(_TABLE_NAME, payload, on_conflict="agent_id")
    except Exception as exc:
        logger.error("[AGENT_MODELS] Failed to save override for %s: %s", agent_id, exc)
        raise


def delete_agent_model_override(agent_id: str) -> None:
    try:
        get_supabase_client().delete(_TABLE_NAME, {"agent_id": agent_id})
    except Exception as exc:
        logger.error("[AGENT_MODELS] Failed to delete override for %s: %s", agent_id, exc)
        raise
