"""
Serviço determinístico de memória do usuário.

get_user_memory()    — busca memória do usuário no Supabase
update_user_memory() — resume fatos estáveis sem depender de agente configurável
"""

import logging
import re
from datetime import datetime, timezone

from backend.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_TABLE = "user_memory"
_MAX_MEMORY_CHARS = 1500
_MAX_FACTS = 16
_STABLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("nome", re.compile(r"\b(?:meu nome é|me chamo|pode me chamar de)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{1,60})", re.IGNORECASE)),
    ("empresa", re.compile(r"\b(?:minha empresa é|trabalho na|trabalho no|sou da|sou do|empresa:)\s+([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s&.'/-]{1,80})", re.IGNORECASE)),
    ("cargo", re.compile(r"\b(?:sou|atuo como|trabalho como)\s+(?:um|uma)?\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s'-]{2,60})", re.IGNORECASE)),
    ("objetivo", re.compile(r"\b(?:quero|preciso|nosso objetivo é|meu objetivo é)\s+([^.!?\n]{8,140})", re.IGNORECASE)),
    ("preferência", re.compile(r"\b(?:prefiro|gosto de|quero sempre)\s+([^.!?\n]{6,120})", re.IGNORECASE)),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_user_memory(user_id: str) -> str:
    """Retorna a memória acumulada do usuário como string vazia se não existir."""
    if not user_id:
        return ""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"user_id": user_id})
        if rows:
            return rows[0].get("content", "") or ""
        return ""
    except Exception as e:
        logger.warning(f"[MEMORY] Falha ao buscar memória de {user_id}: {e}")
        return ""


async def update_user_memory(user_id: str, conversation_text: str) -> None:
    """
    Extrai fatos permanentes da conversa e agrega à memória existente.
    O resumo é determinístico: usa padrões simples, deduplicação e truncamento.
    """
    if not user_id or not conversation_text.strip():
        return

    existing_memory = get_user_memory(user_id)

    try:
        new_memory = _build_memory_snapshot(existing_memory, conversation_text)
        if not new_memory.strip():
            return

        db = get_supabase_client()
        db.upsert(
            _TABLE,
            {
                "user_id": user_id,
                "content": new_memory,
                "updated_at": _now_iso(),
            },
            on_conflict="user_id",
        )

        logger.info(
            f"[MEMORY] Memória atualizada para {user_id} ({len(new_memory)} chars)"
        )

    except Exception as e:
        logger.error(f"[MEMORY] Falha ao atualizar memória de {user_id}: {e}")


def _normalize_fact(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" -:\n\t")).strip()


def _extract_facts(conversation_text: str) -> list[str]:
    facts: list[str] = []
    for label, pattern in _STABLE_PATTERNS:
        for match in pattern.finditer(conversation_text):
            value = _normalize_fact(match.group(1))
            if len(value) < 3:
                continue
            facts.append(f"{label}: {value[:120]}")
    return facts


def _parse_existing_memory(existing_memory: str) -> list[str]:
    if not existing_memory.strip():
        return []
    lines: list[str] = []
    for line in existing_memory.splitlines():
        clean = _normalize_fact(line.lstrip("-•"))
        if clean:
            lines.append(clean)
    return lines


def _build_memory_snapshot(existing_memory: str, conversation_text: str) -> str:
    combined: list[str] = []
    seen: set[str] = set()

    for fact in [*_parse_existing_memory(existing_memory), *_extract_facts(conversation_text)]:
        key = fact.casefold()
        if key in seen:
            continue
        seen.add(key)
        combined.append(fact)
        if len(combined) >= _MAX_FACTS:
            break

    if not combined:
        return existing_memory[:_MAX_MEMORY_CHARS]

    snapshot = "\n".join(f"- {fact}" for fact in combined)
    return snapshot[:_MAX_MEMORY_CHARS]
