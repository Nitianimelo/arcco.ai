"""
API de Projetos.

Endpoints:
  GET    /api/agent/projects?user_id=              → listar projetos
  POST   /api/agent/projects                       → criar projeto
  PUT    /api/agent/projects/{id}                  → atualizar nome/instruções
  DELETE /api/agent/projects/{id}                  → deletar (cascade project_files)
  POST   /api/agent/projects/{id}/files            → upload multipart (extração em background)
  GET    /api/agent/projects/{id}/files            → listar arquivos
  DELETE /api/agent/projects/{id}/files/{file_id}  → deletar arquivo
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from backend.core.supabase_client import get_supabase_client
from backend.models.schemas import (
    ProjectCreate,
    ProjectFileResponse,
    ProjectResponse,
    ProjectUpdate,
)
from backend.services.project_file_service import (
    delete_project_file,
    extract_and_store_project_file,
    get_project_files,
    get_project_file,
    upload_project_file,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_TABLE = "projects"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, user_id: str = Query(...)):
    """Retorna um projeto pelo ID."""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"id": project_id, "user_id": user_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        row = rows[0]
        return ProjectResponse(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            instructions=row.get("instructions", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao buscar {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_projects(user_id: str = Query(...)):
    """Lista projetos do usuário ordenados por atualização."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id é obrigatório")
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"user_id": user_id}, order="updated_at.desc")
        return {"projects": rows}
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao listar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects", response_model=ProjectResponse)
async def create_project(body: ProjectCreate):
    """Cria um novo projeto."""
    try:
        db = get_supabase_client()
        now = _now_iso()
        row = db.insert(
            _TABLE,
            {
                "user_id": body.user_id,
                "name": body.name,
                "instructions": body.instructions or "",
                "created_at": now,
                "updated_at": now,
            },
        )
        return ProjectResponse(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            instructions=row.get("instructions", ""),
            created_at=row.get("created_at", now),
            updated_at=row.get("updated_at", now),
        )
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao criar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, body: ProjectUpdate, user_id: str = Query(...)):
    """Atualiza nome e/ou instruções de um projeto."""
    try:
        db = get_supabase_client()
        existing = db.query(_TABLE, filters={"id": project_id, "user_id": user_id}, limit=1)
        if not existing:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        now = _now_iso()
        data: dict = {"updated_at": now}
        if body.name is not None:
            data["name"] = body.name
        if body.instructions is not None:
            data["instructions"] = body.instructions

        rows = db.update(_TABLE, data, {"id": project_id, "user_id": user_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        row = rows[0]
        return ProjectResponse(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            instructions=row.get("instructions", ""),
            created_at=row.get("created_at", now),
            updated_at=row.get("updated_at", now),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao atualizar {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user_id: str = Query(...)):
    """Deleta projeto e todos os seus arquivos (cascade)."""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"id": project_id, "user_id": user_id}, limit=1)
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        # As conversas do projeto não devem migrar para o histórico geral.
        db.delete("conversations", {"project_id": project_id})
        db.delete(_TABLE, {"id": project_id, "user_id": user_id})
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao deletar {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/files")
async def upload_file(
    project_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Query(...),
    file: UploadFile = File(...),
):
    """Upload de arquivo para o projeto. Extração de texto ocorre em background."""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"id": project_id, "user_id": user_id})
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")

        content = await file.read()
        mime_type = file.content_type or "application/octet-stream"
        filename = file.filename or "arquivo"

        file_id = upload_project_file(
            project_id=project_id,
            user_id=user_id,
            content=content,
            filename=filename,
            mime_type=mime_type,
        )

        background_tasks.add_task(extract_and_store_project_file, file_id)

        return {
            "file_id": file_id,
            "file_name": filename,
            "status": "processing",
            "message": "Arquivo enviado. Extração em andamento.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro no upload para {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/files")
async def list_project_files(project_id: str, user_id: str = Query(...)):
    """Lista arquivos de um projeto."""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"id": project_id, "user_id": user_id}, limit=1)
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        files = get_project_files(project_id)
        return {"files": files}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao listar arquivos de {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/files/{file_id}")
async def delete_file(project_id: str, file_id: str, user_id: str = Query(...)):
    """Deleta arquivo do projeto (storage + DB + chunks)."""
    try:
        db = get_supabase_client()
        rows = db.query(_TABLE, filters={"id": project_id, "user_id": user_id}, limit=1)
        if not rows:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        file_row = get_project_file(file_id)
        if not file_row or file_row.get("project_id") != project_id:
            raise HTTPException(status_code=404, detail="Arquivo não encontrado no projeto")
        delete_project_file(file_id)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PROJECTS] Erro ao deletar arquivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
