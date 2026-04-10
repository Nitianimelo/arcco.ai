"""
Serviço de arquivos efêmeros por sessão.

Responsável por:
- criar e manter o diretório `/tmp/arcco_chat/{session_id}/`
- validar limites por arquivo e por sessão
- persistir e ler `manifest.json`
- limpar sessões explicitamente
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

SESSION_ROOT = Path("/tmp/arcco_chat")
MANIFEST_FILENAME = "manifest.json"
MAX_FILES_PER_SESSION = 10
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class SessionFileError(Exception):
    """Erro base do serviço de sessão."""


class SessionLimitError(SessionFileError):
    """Limites excedidos para a sessão."""


class SessionNotFoundError(SessionFileError):
    """Sessão não encontrada."""


class SessionFileNotFoundError(SessionFileError):
    """Arquivo da sessão não encontrado."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ensure_root_dir() -> None:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)


def validate_session_id(session_id: str) -> str:
    if not session_id or not SESSION_ID_PATTERN.fullmatch(session_id):
        raise SessionFileError(
            "session_id inválido. Use apenas letras, números, hífen e underscore."
        )
    return session_id


def sanitize_filename(filename: str) -> str:
    base_name = Path(filename or "arquivo").name
    sanitized = FILENAME_SANITIZE_PATTERN.sub("_", base_name).strip("._")
    return sanitized or "arquivo"


def get_session_dir(session_id: str) -> Path:
    validate_session_id(session_id)
    return SESSION_ROOT / session_id


def get_manifest_path(session_id: str) -> Path:
    return get_session_dir(session_id) / MANIFEST_FILENAME


def _default_manifest(session_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "files": [],
    }


def load_manifest(session_id: str) -> dict[str, Any]:
    manifest_path = get_manifest_path(session_id)
    if not manifest_path.exists():
        return _default_manifest(session_id)

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Manifesto inválido")
        data.setdefault("session_id", session_id)
        data.setdefault("files", [])
        data.setdefault("created_at", utc_now_iso())
        data["updated_at"] = data.get("updated_at") or utc_now_iso()
        return data
    except Exception as exc:
        logger.error("Falha ao carregar manifesto da sessão %s: %s", session_id, exc)
        raise SessionFileError("Não foi possível ler o manifesto da sessão.") from exc


def save_manifest(session_id: str, manifest: dict[str, Any]) -> None:
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    manifest["session_id"] = session_id
    manifest["updated_at"] = utc_now_iso()

    manifest_path = get_manifest_path(session_id)
    tmp_path = manifest_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(manifest_path)
    except Exception as exc:
        logger.error("Falha ao salvar manifesto da sessão %s: %s", session_id, exc)
        raise SessionFileError("Não foi possível salvar o manifesto da sessão.") from exc


def touch_session(session_id: str) -> None:
    manifest = load_manifest(session_id)
    save_manifest(session_id, manifest)


def list_session_files(session_id: str) -> list[dict[str, Any]]:
    manifest = load_manifest(session_id)
    return list(manifest.get("files", []))


def count_session_files(session_id: str) -> int:
    return len(list_session_files(session_id))


def validate_upload_limits(session_id: str, file_size: int) -> None:
    if file_size <= 0:
        raise SessionLimitError("Arquivo vazio não é permitido.")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise SessionLimitError("Arquivo excede o limite de 100MB.")

    current_count = count_session_files(session_id)
    if current_count >= MAX_FILES_PER_SESSION:
        raise SessionLimitError("A sessão já possui 10 arquivos anexados.")


def save_uploaded_file(
    session_id: str,
    original_name: str,
    content: bytes,
    mime_type: str,
) -> dict[str, Any]:
    validate_session_id(session_id)
    validate_upload_limits(session_id, len(content))
    _ensure_root_dir()

    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid4().hex
    original_basename = Path(original_name or "arquivo").name or "arquivo"
    sanitized_name = sanitize_filename(original_basename)
    stored_filename = f"{file_id}_{sanitized_name}"
    stored_path = session_dir / stored_filename
    extracted_filename = f"{stored_path.stem}_extracted.txt"
    extracted_path = session_dir / extracted_filename

    try:
        stored_path.write_bytes(content)
    except Exception as exc:
        logger.error("Falha ao salvar arquivo %s na sessão %s: %s", original_name, session_id, exc)
        raise SessionFileError("Não foi possível salvar o arquivo enviado.") from exc

    manifest = load_manifest(session_id)
    entry = {
        "file_id": file_id,
        "original_name": original_basename,
        "stored_path": str(stored_path),
        "extracted_text_path": str(extracted_path),
        "mime_type": mime_type or "application/octet-stream",
        "size_bytes": len(content),
        "status": "uploaded",
        "created_at": utc_now_iso(),
        "processed_at": None,
        "error": None,
    }
    manifest.setdefault("files", []).append(entry)
    save_manifest(session_id, manifest)

    logger.info(
        "Arquivo salvo na sessão %s: %s (%s bytes)",
        session_id,
        entry["original_name"],
        entry["size_bytes"],
    )
    return entry


def _update_file_entry(
    session_id: str,
    file_id: str,
    *,
    status: str,
    processed_at: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(session_id)
    files = manifest.get("files", [])

    for entry in files:
        if entry.get("file_id") != file_id:
            continue
        entry["status"] = status
        entry["processed_at"] = processed_at
        entry["error"] = error
        save_manifest(session_id, manifest)
        return entry

    raise SessionFileNotFoundError(f"Arquivo {file_id} não encontrado na sessão {session_id}.")


def mark_file_processing(session_id: str, file_id: str) -> dict[str, Any]:
    logger.info("Marcando arquivo %s da sessão %s como processing", file_id, session_id)
    return _update_file_entry(session_id, file_id, status="processing", error=None)


def mark_file_ready(session_id: str, file_id: str) -> dict[str, Any]:
    logger.info("Marcando arquivo %s da sessão %s como ready", file_id, session_id)
    return _update_file_entry(
        session_id,
        file_id,
        status="ready",
        processed_at=utc_now_iso(),
        error=None,
    )


def mark_file_failed(session_id: str, file_id: str, error: str) -> dict[str, Any]:
    logger.error(
        "Marcando arquivo %s da sessão %s como failed: %s",
        file_id,
        session_id,
        error,
    )
    return _update_file_entry(
        session_id,
        file_id,
        status="failed",
        processed_at=utc_now_iso(),
        error=error[:500],
    )


def get_session_file(session_id: str, file_id: str) -> dict[str, Any]:
    manifest = load_manifest(session_id)
    for entry in manifest.get("files", []):
        if entry.get("file_id") == file_id:
            return entry
    raise SessionFileNotFoundError(f"Arquivo {file_id} não encontrado na sessão {session_id}.")


def get_session_file_by_name(session_id: str, file_name: str) -> dict[str, Any]:
    target_name = Path(file_name or "").name.strip().lower()
    if not target_name:
        raise SessionFileNotFoundError("Nome do arquivo não informado.")

    manifest = load_manifest(session_id)
    for entry in manifest.get("files", []):
        original_name = str(entry.get("original_name", "")).strip().lower()
        if original_name == target_name:
            return entry
    raise SessionFileNotFoundError(
        f"Arquivo '{file_name}' não encontrado na sessão {session_id}."
    )


def get_session_inventory(session_id: str) -> list[dict[str, str]]:
    manifest = load_manifest(session_id)
    inventory: list[dict[str, str]] = []
    for entry in manifest.get("files", []):
        inventory.append(
            {
                "file_name": str(entry.get("original_name", "")),
                "status": str(entry.get("status", "uploaded")),
            }
        )
    return inventory


def delete_session_dir(session_id: str) -> None:
    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        raise SessionNotFoundError(f"Sessão {session_id} não encontrada.")

    try:
        for path in sorted(session_dir.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        session_dir.rmdir()
        logger.info("Sessão %s removida de %s", session_id, session_dir)
    except Exception as exc:
        logger.error("Falha ao remover sessão %s: %s", session_id, exc)
        raise SessionFileError("Não foi possível remover a sessão.") from exc


def session_exists(session_id: str) -> bool:
    return get_session_dir(session_id).exists()


def get_stored_file_path(session_id: str, file_id: str) -> Path:
    entry = get_session_file(session_id, file_id)
    return Path(entry["stored_path"])


def get_extracted_file_path(session_id: str, file_id: str) -> Path:
    entry = get_session_file(session_id, file_id)
    return Path(entry["extracted_text_path"])


def ensure_manifest_exists(session_id: str) -> None:
    if not session_exists(session_id):
        session_dir = get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(session_id)
    save_manifest(session_id, manifest)
