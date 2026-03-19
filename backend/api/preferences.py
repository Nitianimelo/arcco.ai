"""
API de Preferências do Usuário.

Endpoints:
  GET /api/preferences/{user_id}  → retorna preferências (cria default se não existir)
  PUT /api/preferences/{user_id}  → upsert de preferências
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.core.supabase_client import get_supabase_client
from backend.models.schemas import PreferencesUpsert, PreferencesResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_TABLE = "user_preferences"

_DEFAULTS = {
    "theme": "dark",
    "display_name": None,
    "custom_instructions": None,
    "logo_url": None,
    "occupation": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/preferences/{user_id}", response_model=PreferencesResponse)
async def get_preferences(user_id: str):
    """Retorna as preferências do usuário. Cria registro default se não existir."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id é obrigatório")

    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"user_id": user_id})

        if rows:
            row = rows[0]
            return PreferencesResponse(
                user_id=row["user_id"],
                theme=row.get("theme") or "dark",
                display_name=row.get("display_name"),
                custom_instructions=row.get("custom_instructions"),
                logo_url=row.get("logo_url"),
                occupation=row.get("occupation"),
                updated_at=row.get("updated_at", _now_iso()),
            )

        # Cria default
        now = _now_iso()
        new_row = db.upsert(_TABLE, {"user_id": user_id, **_DEFAULTS, "updated_at": now})
        return PreferencesResponse(
            user_id=user_id,
            theme="dark",
            display_name=None,
            custom_instructions=None,
            logo_url=None,
            occupation=None,
            updated_at=now,
        )

    except Exception as e:
        logger.error(f"[PREFERENCES] Erro ao buscar preferências de {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/preferences/{user_id}", response_model=PreferencesResponse)
async def upsert_preferences(user_id: str, body: PreferencesUpsert):
    """Cria ou atualiza as preferências do usuário."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id é obrigatório")

    try:
        db = get_supabase_client()
        now = _now_iso()

        # Monta dict só com campos que foram enviados (não None implica mudança)
        data: dict = {"user_id": user_id, "updated_at": now}
        if body.theme is not None:
            data["theme"] = body.theme
        if body.display_name is not None:
            data["display_name"] = body.display_name
        if body.custom_instructions is not None:
            data["custom_instructions"] = body.custom_instructions
        if body.logo_url is not None:
            data["logo_url"] = body.logo_url
        if body.occupation is not None:
            data["occupation"] = body.occupation

        db.upsert(_TABLE, data, on_conflict="user_id")

        # Busca resultado atualizado
        rows = db.query(_TABLE, filters={"user_id": user_id})
        row = rows[0] if rows else data
        return PreferencesResponse(
            user_id=user_id,
            theme=row.get("theme") or "dark",
            display_name=row.get("display_name"),
            custom_instructions=row.get("custom_instructions"),
            logo_url=row.get("logo_url"),
            occupation=row.get("occupation"),
            updated_at=row.get("updated_at", now),
        )

    except Exception as e:
        logger.error(f"[PREFERENCES] Erro ao salvar preferências de {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
