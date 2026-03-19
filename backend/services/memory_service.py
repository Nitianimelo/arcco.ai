"""
Serviço de Memória Acumulativa do Usuário.

get_user_memory()    — busca memória do usuário no Supabase
update_user_memory() — extrai e agrega fatos da conversa via gpt-4o-mini (background)
"""

import logging
from datetime import datetime, timezone

from backend.core.supabase_client import get_supabase_client
from backend.core.llm import call_openrouter

logger = logging.getLogger(__name__)

_TABLE = "user_memory"
_MAX_MEMORY_CHARS = 1500


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
    Usa gpt-4o-mini com síntese comprimida (máx. 1500 chars).
    Chamado em background após cada stream completo.
    """
    if not user_id or not conversation_text.strip():
        return

    existing_memory = get_user_memory(user_id)

    system_prompt = (
        "Você é um sistema de memória. Sua tarefa é agregar os fatos novos "
        "da conversa com a memória existente, removendo redundâncias e "
        "mantendo APENAS fatos permanentes e relevantes sobre o usuário: "
        "profissão, empresa, objetivos de negócio, preferências estáveis, "
        "nomes de pessoas/produtos relevantes.\n"
        "REGRA RÍGIDA: o resultado final deve ter no MÁXIMO 1500 caracteres. "
        "Sintetize, comprima e elimine informação transitória (tarefas "
        "pontuais já feitas, perguntas genéricas, etc.).\n"
        f"Memória existente:\n{existing_memory or '(vazia)'}\n\n"
        f"Conversa nova:\n{conversation_text[:3000]}\n\n"
        "Retorne APENAS a memória atualizada, sem prefixos nem explicações."
    )

    try:
        response = await call_openrouter(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Atualize a memória."},
            ],
            model="openai/gpt-4o-mini",
            max_tokens=600,
            temperature=0.1,
        )

        new_memory = ""
        if response and "choices" in response:
            new_memory = response["choices"][0]["message"]["content"].strip()

        if not new_memory:
            return

        # Trunca para garantir limite
        new_memory = new_memory[:_MAX_MEMORY_CHARS]

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
