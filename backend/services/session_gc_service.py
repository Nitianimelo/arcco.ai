"""
Garbage collection por TTL para sessões efêmeras.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from backend.services.session_file_service import (
    SESSION_ROOT,
    delete_session_dir,
    load_manifest,
    parse_iso_datetime,
)

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TTL_SECONDS = int(os.getenv("CHAT_SESSION_TTL_SECONDS", "3600"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def cleanup_expired_sessions(
    base_dir: Path = SESSION_ROOT,
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
) -> int:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds deve ser maior que zero.")

    if not base_dir.exists():
        return 0

    removed = 0
    for session_dir in base_dir.iterdir():
        if not session_dir.is_dir():
            continue

        session_id = session_dir.name
        try:
            manifest = load_manifest(session_id)
            updated_at_raw = str(manifest.get("updated_at") or manifest.get("created_at"))
            updated_at = parse_iso_datetime(updated_at_raw)
            age_seconds = (_now_utc() - updated_at).total_seconds()
            if age_seconds > ttl_seconds:
                delete_session_dir(session_id)
                removed += 1
                logger.info(
                    "Sessão expirada removida: %s (idade %.0fs, ttl=%ss)",
                    session_id,
                    age_seconds,
                    ttl_seconds,
                )
        except Exception as exc:
            logger.error("Falha ao avaliar/remover sessão %s: %s", session_id, exc)
    return removed
