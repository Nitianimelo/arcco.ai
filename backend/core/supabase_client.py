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
        # Singleton HTTP client — reutiliza conexão TCP/TLS em vez de criar uma nova a cada query
        self._http = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

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

        response = self._http.post(
            upload_url,
            headers={
                **self.headers,
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=file_content,
            timeout=60.0,
        )

        if response.status_code not in (200, 201):
            logger.error(f"Upload failed ({response.status_code}): {response.text}")
            raise Exception(f"Supabase upload failed: {response.text}")

        public_url = f"{self.url}/storage/v1/object/public/{bucket}/{path}"
        return public_url

    # ── PostgREST ─────────────────────────────────────

    def query(
        self,
        table: str,
        select: str = "*",
        filters: Optional[dict] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list:
        """Query simples via PostgREST. Suporta filtros eq., order e limit."""
        url = f"{self.url}/rest/v1/{table}?select={select}"

        if filters:
            for key, value in filters.items():
                if value is None:
                    url += f"&{key}=is.null"
                else:
                    url += f"&{key}=eq.{value}"
        if order:
            url += f"&order={order}"
        if limit:
            url += f"&limit={limit}"

        response = self._http.get(url, headers=self.headers)
        if response.status_code != 200:
            logger.error(f"Query failed: {response.text}")
            return []
        return response.json()

    def insert(self, table: str, data: dict) -> dict:
        """Insert de uma row via PostgREST. Retorna a row criada."""
        url = f"{self.url}/rest/v1/{table}"
        response = self._http.post(
            url,
            headers={
                **self.headers,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=data,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Supabase insert failed ({response.status_code}): {response.text}")
        result = response.json()
        return result[0] if isinstance(result, list) else result

    def insert_many(self, table: str, rows: list) -> list:
        """Insert de múltiplas rows via PostgREST. Retorna as rows criadas."""
        if not rows:
            return []
        url = f"{self.url}/rest/v1/{table}"
        response = self._http.post(
            url,
            headers={
                **self.headers,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=rows,
            timeout=60.0,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Supabase insert_many failed ({response.status_code}): {response.text}")
        return response.json()

    def update(self, table: str, data: dict, filters: dict) -> list:
        """Update de rows que atendem os filtros. Retorna rows atualizadas."""
        url = f"{self.url}/rest/v1/{table}"
        if filters:
            params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
            url = f"{url}?{params}"
        response = self._http.patch(
            url,
            headers={
                **self.headers,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=data,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Supabase update failed ({response.status_code}): {response.text}")
        return response.json() if response.status_code == 200 else []

    def upsert(self, table: str, data: dict, on_conflict: str = "") -> dict:
        """Upsert (insert or update) via PostgREST. Retorna a row resultante."""
        url = f"{self.url}/rest/v1/{table}"
        if on_conflict:
            url = f"{url}?on_conflict={on_conflict}"
        response = self._http.post(
            url,
            headers={
                **self.headers,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
            json=data,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Supabase upsert failed ({response.status_code}): {response.text}")
        result = response.json()
        return result[0] if isinstance(result, list) else result

    def delete(self, table: str, filters: dict) -> None:
        """Delete de rows que atendem os filtros."""
        url = f"{self.url}/rest/v1/{table}"
        if filters:
            params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
            url = f"{url}?{params}"
        response = self._http.delete(url, headers=self.headers)
        if response.status_code not in (200, 204):
            raise Exception(f"Supabase delete failed ({response.status_code}): {response.text}")

    def rpc(self, function_name: str, params: dict) -> list:
        """Chama uma função RPC (stored procedure) do Supabase."""
        url = f"{self.url}/rest/v1/rpc/{function_name}"
        response = self._http.post(
            url,
            headers={**self.headers, "Content-Type": "application/json"},
            json=params,
        )
        if response.status_code != 200:
            raise Exception(f"Supabase RPC failed ({response.status_code}): {response.text}")
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
