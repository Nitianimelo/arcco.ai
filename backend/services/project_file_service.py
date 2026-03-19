"""
Serviço de upload e extração de arquivos de projetos.

upload_project_file()           — recebe bytes, faz upload ao bucket 'project-files',
                                   insere row em project_files, retorna file_id
extract_and_store_project_file() — background task: baixa arquivo, extrai texto,
                                   salva no DB, chunka e indexa no FTS
get_project_files()              — lista arquivos de um projeto
delete_project_file()            — remove storage + row (cascade destrói chunks)
"""

import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.core.supabase_client import get_supabase_client
from backend.services.session_extraction_service import extract_text_for_file
from backend.services.project_rag_service import insert_chunks_for_file

logger = logging.getLogger(__name__)

_BUCKET = "project-files"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upload_project_file(
    project_id: str,
    user_id: str,
    content: bytes,
    filename: str,
    mime_type: str = "application/octet-stream",
) -> str:
    """
    Faz upload do arquivo ao bucket 'project-files', insere row em project_files.
    Retorna o file_id (UUID) da row criada.
    """
    db = get_supabase_client()

    file_id = str(uuid.uuid4())
    storage_path = f"{project_id}/{file_id}/{filename}"

    # Upload para Supabase Storage
    db.storage_upload(_BUCKET, storage_path, content, mime_type)

    # Insere row em project_files
    now = _now_iso()
    db.insert(
        "project_files",
        {
            "id": file_id,
            "project_id": project_id,
            "user_id": user_id,
            "file_name": filename,
            "storage_path": storage_path,
            "mime_type": mime_type,
            "size_bytes": len(content),
            "status": "processing",
            "created_at": now,
        },
    )

    return file_id


def extract_and_store_project_file(project_file_id: str) -> None:
    """
    Background task: baixa arquivo do Supabase Storage, extrai texto,
    salva no DB com status='ready', chunka e indexa no FTS.
    """
    db = get_supabase_client()

    # Busca metadados do arquivo
    rows = db.query("project_files", filters={"id": project_file_id})
    if not rows:
        logger.error(f"[PROJECT_FILE] Arquivo não encontrado: {project_file_id}")
        return

    row = rows[0]
    storage_path = row["storage_path"]
    mime_type = row.get("mime_type", "application/octet-stream")
    filename = row["file_name"]
    project_id = row["project_id"]

    # Download do Supabase Storage (usa service role key)
    download_url = f"{db.url}/storage/v1/object/{_BUCKET}/{storage_path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(download_url, headers=db.headers)
        if response.status_code != 200:
            raise Exception(
                f"Download falhou ({response.status_code}): {response.text[:200]}"
            )
        file_bytes = response.content
    except Exception as e:
        logger.error(f"[PROJECT_FILE] Falha ao baixar {project_file_id}: {e}")
        db.update(
            "project_files",
            {"status": "failed", "error_message": str(e)[:500]},
            {"id": project_file_id},
        )
        return

    # Salva em arquivo temporário para extração
    suffix = Path(filename).suffix.lower() or ".bin"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = Path(tmp.name)

        extracted_text = extract_text_for_file(tmp_path, mime_type)
    except Exception as e:
        logger.error(f"[PROJECT_FILE] Falha na extração {project_file_id}: {e}")
        db.update(
            "project_files",
            {"status": "failed", "error_message": str(e)[:500]},
            {"id": project_file_id},
        )
        return
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    # Indexa no FTS (chunks são a única representação persistente do conteúdo)
    try:
        insert_chunks_for_file(project_file_id, project_id, extracted_text)
        logger.info(f"[PROJECT_FILE] Arquivo {project_file_id} indexado com sucesso.")
    except Exception as e:
        logger.error(f"[PROJECT_FILE] Falha ao indexar chunks de {project_file_id}: {e}")
        db.update(
            "project_files",
            {"status": "failed", "error_message": str(e)[:500]},
            {"id": project_file_id},
        )
        return

    # Marca como ready e limpa o texto bruto (chunks já estão no FTS, não precisa mais)
    db.update(
        "project_files",
        {"status": "ready", "extracted_text": None, "storage_path": ""},
        {"id": project_file_id},
    )

    # Deleta o arquivo original do Storage — o RAG já está salvo nos chunks
    if storage_path:
        try:
            delete_url = f"{db.url}/storage/v1/object/{_BUCKET}"
            with httpx.Client(timeout=30.0) as client:
                client.delete(
                    delete_url,
                    headers={**db.headers, "Content-Type": "application/json"},
                    json={"prefixes": [storage_path]},
                )
            logger.info(f"[PROJECT_FILE] Arquivo original deletado do storage: {storage_path}")
        except Exception as e:
            logger.warning(f"[PROJECT_FILE] Falha ao deletar do storage (não crítico): {e}")


def get_project_files(project_id: str) -> list:
    """Retorna lista de arquivos de um projeto."""
    db = get_supabase_client()
    return db.query(
        "project_files",
        select="id,project_id,user_id,file_name,mime_type,size_bytes,status,error_message,created_at",
        filters={"project_id": project_id},
        order="created_at.desc",
    )


def delete_project_file(project_file_id: str) -> None:
    """Remove row do DB (cascade destrói chunks). Storage já foi limpo após processamento."""
    db = get_supabase_client()

    # Tenta deletar do storage caso o arquivo ainda esteja lá (ex: falhou durante processamento)
    rows = db.query("project_files", filters={"id": project_file_id})
    if rows:
        storage_path = rows[0].get("storage_path", "")
        if storage_path:
            try:
                delete_url = f"{db.url}/storage/v1/object/{_BUCKET}"
                with httpx.Client(timeout=30.0) as client:
                    client.delete(
                        delete_url,
                        headers={**db.headers, "Content-Type": "application/json"},
                        json={"prefixes": [storage_path]},
                    )
            except Exception as e:
                logger.warning(f"[PROJECT_FILE] Falha ao deletar do storage: {e}")

    db.delete("project_files", {"id": project_file_id})
