import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from backend.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        json.dumps(value)
        return value
    except Exception:
        return {"repr": repr(value)}


def _looks_like_uuid(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", value.strip()))


class ExecutionLogService:
    def __init__(self):
        self._agent_sequence = 0
        self._log_sequence = 0

    async def create_execution(
        self,
        *,
        conversation_id: str | None,
        session_id: str | None,
        project_id: str | None,
        user_id: str | None,
        request_text: str,
        request_source: str,
        supervisor_agent: str = "chat",
        metadata: dict[str, Any] | None = None,
        model_used: str | None = None,
    ) -> str | None:
        safe_metadata = dict(metadata or {})
        normalized_user_id = user_id if _looks_like_uuid(user_id) else None
        normalized_project_id = project_id if _looks_like_uuid(project_id) else None
        if user_id is not None and normalized_user_id is None:
            safe_metadata["original_user_id"] = str(user_id)
        if project_id is not None and normalized_project_id is None:
            safe_metadata["original_project_id"] = str(project_id)

        payload = {
            "conversation_id": conversation_id,
            "session_id": session_id,
            "project_id": normalized_project_id,
            "user_id": normalized_user_id,
            "request_text": request_text or "",
            "request_source": request_source,
            "supervisor_agent": supervisor_agent,
            "status": "running",
            "metadata": _safe_json(safe_metadata),
            "started_at": _now_iso(),
            "created_at": _now_iso(),
        }
        if model_used:
            payload["model_used"] = model_used
        try:
            row = await asyncio.to_thread(get_supabase_client().insert, "agent_executions", payload)
            return row.get("id")
        except Exception as exc:
            logger.warning("[EXEC-LOG] create_execution failed: %s", exc)

            # Compatibilidade com schemas antigos criados com user_id/project_id como uuid.
            fallback_payload = dict(payload)
            fallback_metadata = dict(metadata or {})
            if user_id is not None:
                fallback_metadata["original_user_id"] = str(user_id)
                fallback_payload["user_id"] = None
            if project_id is not None:
                fallback_metadata["original_project_id"] = str(project_id)
                fallback_payload["project_id"] = None
            fallback_payload["metadata"] = _safe_json(fallback_metadata)

            try:
                row = await asyncio.to_thread(get_supabase_client().insert, "agent_executions", fallback_payload)
                logger.warning("[EXEC-LOG] create_execution fallback insert succeeded without typed user/project ids")
                return row.get("id")
            except Exception as fallback_exc:
                logger.warning("[EXEC-LOG] create_execution fallback failed: %s", fallback_exc)
                return None

    async def finish_execution(
        self,
        execution_id: str | None,
        *,
        status: str,
        final_error: str | None = None,
        metadata: dict[str, Any] | None = None,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
    ) -> None:
        if not execution_id:
            return
        payload = {
            "status": status,
            "final_error": final_error,
            "finished_at": _now_iso(),
        }
        if metadata is not None:
            merged_metadata = dict(await self.get_execution_metadata(execution_id))
            merged_metadata.update(metadata)
            payload["metadata"] = _safe_json(merged_metadata)
        if total_tokens:
            payload["total_tokens"] = total_tokens
        if total_cost_usd:
            payload["total_cost_usd"] = round(total_cost_usd, 6)
        try:
            await asyncio.to_thread(get_supabase_client().update, "agent_executions", payload, {"id": execution_id})
        except Exception as exc:
            logger.warning("[EXEC-LOG] finish_execution failed: %s", exc)

    async def get_execution_metadata(self, execution_id: str | None) -> dict[str, Any]:
        if not execution_id:
            return {}
        try:
            rows = await asyncio.to_thread(
                get_supabase_client().query,
                "agent_executions",
                "metadata",
                {"id": execution_id},
                "created_at.desc",
                1,
            )
            if rows and isinstance(rows[0].get("metadata"), dict):
                return rows[0]["metadata"]
        except Exception as exc:
            logger.warning("[EXEC-LOG] get_execution_metadata failed: %s", exc)
        return {}

    async def start_agent(
        self,
        execution_id: str | None,
        *,
        agent_key: str,
        agent_name: str,
        model: str | None = None,
        role: str | None = None,
        route: str | None = None,
        input_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if not execution_id:
            return None
        self._agent_sequence += 1
        payload = {
            "execution_id": execution_id,
            "agent_key": agent_key,
            "agent_name": agent_name,
            "model": model,
            "role": role,
            "route": route,
            "sequence_no": self._agent_sequence,
            "status": "running",
            "input_payload": _safe_json(input_payload or {}),
            "metadata": _safe_json(metadata or {}),
            "started_at": _now_iso(),
            "created_at": _now_iso(),
        }
        try:
            row = await asyncio.to_thread(get_supabase_client().insert, "agent_execution_agents", payload)
            return row.get("id")
        except Exception as exc:
            logger.warning("[EXEC-LOG] start_agent failed: %s", exc)
            return None

    async def finish_agent(
        self,
        execution_agent_id: str | None,
        *,
        status: str,
        output_payload: dict[str, Any] | None = None,
        error_text: str | None = None,
        metadata: dict[str, Any] | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        if not execution_agent_id:
            return
        payload = {
            "status": status,
            "finished_at": _now_iso(),
            "error_text": error_text,
        }
        if output_payload is not None:
            payload["output_payload"] = _safe_json(output_payload)
        if metadata is not None:
            payload["metadata"] = _safe_json(metadata)
        if prompt_tokens:
            payload["prompt_tokens"] = prompt_tokens
        if completion_tokens:
            payload["completion_tokens"] = completion_tokens
        if total_tokens:
            payload["total_tokens"] = total_tokens
        if estimated_cost_usd:
            payload["estimated_cost_usd"] = round(estimated_cost_usd, 6)
        try:
            await asyncio.to_thread(get_supabase_client().update, "agent_execution_agents", payload, {"id": execution_agent_id})
        except Exception as exc:
            logger.warning("[EXEC-LOG] finish_agent failed: %s", exc)

    async def log_event(
        self,
        execution_id: str | None,
        *,
        execution_agent_id: str | None = None,
        level: str = "info",
        event_type: str,
        message: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        tool_result: Any = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        if not execution_id:
            return
        self._log_sequence += 1
        payload = {
            "execution_id": execution_id,
            "execution_agent_id": execution_agent_id,
            "sequence_no": self._log_sequence,
            "level": level,
            "event_type": event_type,
            "message": message,
            "tool_name": tool_name,
            "tool_args": _safe_json(tool_args),
            "tool_result": _safe_json(tool_result),
            "raw_payload": _safe_json(raw_payload or {}),
            "created_at": _now_iso(),
        }
        try:
            await asyncio.to_thread(get_supabase_client().insert, "agent_execution_logs", payload)
        except Exception as exc:
            logger.warning("[EXEC-LOG] log_event failed: %s", exc)


async def list_execution_summaries(limit: int = 100) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(
            get_supabase_client().query,
            "v_agent_execution_summary",
            "*",
            None,
            "created_at.desc",
            limit,
        )
    except Exception as exc:
        logger.warning("[EXEC-LOG] list_execution_summaries failed: %s", exc)
        return []


async def get_execution_details(execution_id: str) -> dict[str, Any]:
    client = get_supabase_client()
    try:
        execution_rows = await asyncio.to_thread(client.query, "agent_executions", "*", {"id": execution_id}, "created_at.desc", 1)
        agent_rows = await asyncio.to_thread(client.query, "agent_execution_agents", "*", {"execution_id": execution_id}, "sequence_no.asc", 500)
        log_rows = await asyncio.to_thread(client.query, "agent_execution_logs", "*", {"execution_id": execution_id}, "id.asc", 5000)
        return {
            "execution": execution_rows[0] if execution_rows else None,
            "agents": agent_rows,
            "logs": log_rows,
        }
    except Exception as exc:
        logger.warning("[EXEC-LOG] get_execution_details failed: %s", exc)
        return {"execution": None, "agents": [], "logs": []}
