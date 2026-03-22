import logging
import time
import uuid
from typing import Any

from backend.core.supabase_client import get_supabase_client


logger = logging.getLogger(__name__)

_TABLE = "chat_model_configs"
_CACHE_TTL_SECONDS = 30
_chat_models_cache: list[dict[str, Any]] | None = None
_chat_models_cache_ts = 0.0


def _clone(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in items]


def _invalidate_cache() -> None:
    global _chat_models_cache, _chat_models_cache_ts
    _chat_models_cache = None
    _chat_models_cache_ts = 0.0


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "slot_number": int(item.get("slot_number") or 0),
        "model_name": item.get("model_name") or "",
        "openrouter_model_id": item.get("openrouter_model_id") or "",
        "system_prompt": item.get("system_prompt") or "",
        "is_active": bool(item.get("is_active", True)),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }

def _fetch_chat_models() -> list[dict[str, Any]]:
    db = get_supabase_client()
    items = db.query(_TABLE, order="slot_number.asc", limit=100)
    items = [_normalize_item(item) for item in items]
    items.sort(key=lambda item: (int(item.get("slot_number") or 0), str(item.get("model_name") or "").lower()))
    return items


def list_chat_models(force_refresh: bool = False) -> list[dict[str, Any]]:
    global _chat_models_cache, _chat_models_cache_ts

    if (
        not force_refresh
        and _chat_models_cache is not None
        and (time.time() - _chat_models_cache_ts) < _CACHE_TTL_SECONDS
    ):
        return _clone(_chat_models_cache)

    try:
        items = _fetch_chat_models()
        _chat_models_cache = items
        _chat_models_cache_ts = time.time()
        return _clone(items)
    except Exception as exc:
        logger.error(f"[CHAT_MODELS] Failed to load chat models from Supabase: {exc}")
        if _chat_models_cache is not None:
            return _clone(_chat_models_cache)
        return []


def _renumber_slots(items: list[dict[str, Any]]) -> None:
    db = get_supabase_client()
    ordered = sorted(items, key=lambda item: (int(item.get("slot_number") or 0), str(item.get("id") or "")))
    for index, item in enumerate(ordered, start=1):
        if int(item.get("slot_number") or 0) == index:
            continue
        db.update(_TABLE, {"slot_number": index}, {"id": item["id"]})


def create_chat_model(data: dict[str, Any]) -> dict[str, Any]:
    db = get_supabase_client()
    items = list_chat_models(force_refresh=True)
    next_slot = max((int(item.get("slot_number") or 0) for item in items), default=0) + 1

    item = {
        "id": data.get("id") or str(uuid.uuid4()),
        "slot_number": int(data.get("slot_number") or next_slot),
        "model_name": data.get("model_name") or f"Novo modelo {next_slot}",
        "openrouter_model_id": data.get("openrouter_model_id", ""),
        "system_prompt": data.get("system_prompt", ""),
        "is_active": bool(data.get("is_active", True)),
    }

    created = db.insert(_TABLE, item)
    _invalidate_cache()
    return _normalize_item(created)


def update_chat_model(model_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    db = get_supabase_client()
    current = db.query(_TABLE, filters={"id": model_id}, limit=1)
    if not current:
        return None

    current_item = _normalize_item(current[0])
    payload = {
        "model_name": data.get("model_name", current_item.get("model_name", "")),
        "openrouter_model_id": data.get("openrouter_model_id", current_item.get("openrouter_model_id", "")),
        "system_prompt": data.get("system_prompt", current_item.get("system_prompt", "")),
        "is_active": bool(data.get("is_active", current_item.get("is_active", True))),
        "slot_number": int(data.get("slot_number", current_item.get("slot_number", 0))),
    }

    updated_rows = db.update(_TABLE, payload, {"id": model_id})
    _invalidate_cache()
    if updated_rows:
        return _normalize_item(updated_rows[0])
    return _normalize_item({**current_item, **payload})


def delete_chat_model(model_id: str) -> bool:
    db = get_supabase_client()
    current = db.query(_TABLE, filters={"id": model_id}, limit=1)
    if not current:
        return False

    db.delete(_TABLE, {"id": model_id})
    remaining = db.query(_TABLE, order="slot_number.asc", limit=100)
    try:
        _renumber_slots([_normalize_item(item) for item in remaining])
    except Exception as exc:
        logger.warning(f"[CHAT_MODELS] Failed to renumber slots after delete: {exc}")

    _invalidate_cache()
    return True
