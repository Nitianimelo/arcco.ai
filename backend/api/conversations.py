"""
API de Conversações e Mensagens.

Endpoints:
  POST   /api/agent/conversations                       → criar conversa
  GET    /api/agent/conversations?user_id=              → listar (50 mais recentes)
  GET    /api/agent/conversations/{id}/messages         → mensagens de uma conversa
  POST   /api/agent/conversations/{id}/messages         → salvar batch de mensagens
  DELETE /api/agent/conversations/{id}                  → deletar
  PATCH  /api/agent/conversations/{id}/title            → atualizar título
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.core.supabase_client import get_supabase_client
from backend.models.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationTitleUpdate,
    MessagesBatchCreate,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_TABLE = "conversations"
_MSG_TABLE = "messages"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(body: ConversationCreate):
    """Cria uma nova conversa."""
    try:
        db = get_supabase_client()
        now = _now_iso()
        row = db.insert(
            _TABLE,
            {
                "user_id": body.user_id,
                "project_id": body.project_id,
                "title": body.title or "Nova Conversa",
                "created_at": now,
                "updated_at": now,
            },
        )
        return ConversationResponse(
            id=row["id"],
            user_id=row["user_id"],
            project_id=row.get("project_id"),
            title=row.get("title", "Nova Conversa"),
            created_at=row.get("created_at", now),
            updated_at=row.get("updated_at", now),
        )
    except Exception as e:
        logger.error(f"[CONV] Erro ao criar conversa: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    user_id: str = Query(...),
    project_id: str = Query(None),
):
    """Lista as 50 conversas mais recentes do usuário. Filtra por project_id se informado."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id é obrigatório")
    try:
        db = get_supabase_client()
        filters: dict = {"user_id": user_id}
        if project_id:
            filters["project_id"] = project_id
        else:
            # Sem project_id → retorna apenas conversas do chat normal (sem projeto)
            filters["project_id"] = None
        rows = db.query(
            _TABLE,
            filters=filters,
            order="updated_at.desc",
            limit=50,
        )
        return {"conversations": rows}
    except Exception as e:
        logger.error(f"[CONV] Erro ao listar conversas de {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    """Retorna todas as mensagens de uma conversa em ordem cronológica."""
    try:
        db = get_supabase_client()
        rows = db.query(
            _MSG_TABLE,
            filters={"conversation_id": conversation_id},
            order="created_at.asc",
        )
        return {"messages": rows}
    except Exception as e:
        logger.error(f"[CONV] Erro ao buscar mensagens de {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/messages")
async def save_messages(conversation_id: str, body: MessagesBatchCreate):
    """Salva batch de mensagens em uma conversa."""
    try:
        db = get_supabase_client()
        now = _now_iso()
        rows = [
            {
                "conversation_id": conversation_id,
                "role": msg.role,
                "content": msg.content,
                "created_at": now,
            }
            for msg in body.messages
        ]
        if rows:
            db.insert_many(_MSG_TABLE, rows)

        # Atualiza updated_at da conversa
        db.update(_TABLE, {"updated_at": now}, {"id": conversation_id})

        return {"saved": len(rows)}
    except Exception as e:
        logger.error(f"[CONV] Erro ao salvar mensagens em {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Deleta uma conversa e suas mensagens (cascade)."""
    try:
        db = get_supabase_client()
        db.delete(_TABLE, {"id": conversation_id})
        return {"deleted": True}
    except Exception as e:
        logger.error(f"[CONV] Erro ao deletar {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/conversations/{conversation_id}/title")
async def update_title(conversation_id: str, body: ConversationTitleUpdate):
    """Atualiza o título de uma conversa."""
    try:
        db = get_supabase_client()
        now = _now_iso()
        db.update(
            _TABLE,
            {"title": body.title, "updated_at": now},
            {"id": conversation_id},
        )
        return {"updated": True}
    except Exception as e:
        logger.error(f"[CONV] Erro ao atualizar título de {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
