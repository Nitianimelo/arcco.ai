"""
Cliente Supabase via HTTP puro (sem SDK pesado).
Suporta Storage (upload/download) e PostgREST (queries).
"""

import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Cliente leve para Supabase usando httpx."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }

    # ── Storage ───────────────────────────────────────

    def storage_upload(
        self,
        bucket: str,
        path: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload arquivo e retorna URL pública."""
        upload_url = f"{self.url}/storage/v1/object/{bucket}/{path}"

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                upload_url,
                headers={
                    **self.headers,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
                content=file_content,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Upload failed ({response.status_code}): {response.text}")
                raise Exception(f"Supabase upload failed: {response.text}")

        public_url = f"{self.url}/storage/v1/object/public/{bucket}/{path}"
        return public_url

    # ── PostgREST ─────────────────────────────────────

    def query(self, table: str, select: str = "*", filters: Optional[dict] = None) -> list:
        """Query simples via PostgREST."""
        url = f"{self.url}/rest/v1/{table}?select={select}"

        if filters:
            for key, value in filters.items():
                url += f"&{key}=eq.{value}"

        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Query failed: {response.text}")
                return []
            return response.json()


_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Retorna cliente Supabase singleton."""
    global _client
    if _client is None:
        from .config import get_config
        config = get_config()
        if not config.supabase_url or not config.supabase_key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY são necessários")
        _client = SupabaseClient(config.supabase_url, config.supabase_key)
    return _client


def upload_to_supabase(
    bucket: str,
    filename: str,
    file_content: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload arquivo para Supabase Storage e retorna URL pública."""
    client = get_supabase_client()
    timestamped_name = f"{int(time.time())}-{filename}"

    url = client.storage_upload(bucket, timestamped_name, file_content, content_type)
    logger.info(f"Uploaded {filename} ({len(file_content)} bytes) → {url}")
    return url
