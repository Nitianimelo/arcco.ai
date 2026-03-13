import json
import logging
import uuid
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_DATA_FILE = _DATA_DIR / "chat_models.json"


def _ensure_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _DATA_FILE.exists():
        _DATA_FILE.write_text("[]", encoding="utf-8")


def list_chat_models() -> list[dict[str, Any]]:
    _ensure_storage()
    try:
        items = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"[CHAT_MODELS] Failed to read storage: {exc}")
        items = []
    return sorted(items, key=lambda item: item.get("slot_number", 0))


def save_chat_models(items: list[dict[str, Any]]) -> None:
    _ensure_storage()
    _DATA_FILE.write_text(
        json.dumps(sorted(items, key=lambda item: item.get("slot_number", 0)), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_chat_model(data: dict[str, Any]) -> dict[str, Any]:
    items = list_chat_models()
    next_slot = max((item.get("slot_number", 0) for item in items), default=0) + 1
    item = {
        "id": data.get("id") or str(uuid.uuid4()),
        "slot_number": data.get("slot_number") or next_slot,
        "model_name": data.get("model_name") or f"Novo modelo {next_slot}",
        "openrouter_model_id": data.get("openrouter_model_id", ""),
        "system_prompt": data.get("system_prompt", ""),
        "is_active": bool(data.get("is_active", True)),
    }
    items.append(item)
    save_chat_models(items)
    return item


def update_chat_model(model_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    items = list_chat_models()
    updated = None
    for item in items:
        if item.get("id") != model_id:
            continue
        item.update({
            "model_name": data.get("model_name", item.get("model_name", "")),
            "openrouter_model_id": data.get("openrouter_model_id", item.get("openrouter_model_id", "")),
            "system_prompt": data.get("system_prompt", item.get("system_prompt", "")),
            "is_active": bool(data.get("is_active", item.get("is_active", True))),
            "slot_number": int(data.get("slot_number", item.get("slot_number", 0))),
        })
        updated = item
        break

    if not updated:
        return None

    save_chat_models(items)
    return updated


def delete_chat_model(model_id: str) -> bool:
    items = list_chat_models()
    filtered = [item for item in items if item.get("id") != model_id]
    if len(filtered) == len(items):
        return False
    for index, item in enumerate(sorted(filtered, key=lambda row: row.get("slot_number", 0)), start=1):
        item["slot_number"] = index
    save_chat_models(filtered)
    return True
