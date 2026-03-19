"""
Serviço de embeddings via OpenAI text-embedding-3-small.

get_embedding(text)          — embedding de um único texto (1536 floats)
get_embeddings_batch(texts)  — embeddings de múltiplos textos em batch
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_OPENAI_API_URL = "https://api.openai.com/v1/embeddings"
_MODEL = "text-embedding-3-small"
_DIMENSIONS = 1536

# Cache da API key em memória (evita queries repetidas ao Supabase)
_openai_key: Optional[str] = None


def _get_openai_key() -> str:
    """
    Busca a chave da OpenAI do Supabase (tabela ApiKeys, provider='openai').
    Faz fallback para variável de ambiente OPENAI_API_KEY.
    """
    global _openai_key
    if _openai_key:
        return _openai_key

    # Tenta buscar do Supabase
    try:
        from backend.core.supabase_client import get_supabase_client
        db = get_supabase_client()
        rows = db.query(
            "ApiKeys",
            select="api_key",
            filters={"provider": "openai"},
        )
        if rows and rows[0].get("api_key"):
            _openai_key = rows[0]["api_key"]
            logger.info("[EMBEDDING] OpenAI API key carregada do Supabase.")
            return _openai_key
    except Exception as e:
        logger.warning(f"[EMBEDDING] Falha ao buscar chave OpenAI do Supabase: {e}")

    # Fallback: variável de ambiente
    _openai_key = os.getenv("OPENAI_API_KEY", "")
    if not _openai_key:
        raise ValueError(
            "OpenAI API key não encontrada. "
            "Adicione na tabela ApiKeys (provider='openai') ou defina OPENAI_API_KEY."
        )
    return _openai_key


def get_embedding(text: str) -> list[float]:
    """
    Gera embedding para um único texto.
    Retorna lista de 1536 floats.
    """
    return get_embeddings_batch([text])[0]


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Gera embeddings para múltiplos textos em uma única chamada à OpenAI API.
    Máximo recomendado: 100 textos por chamada para controlar rate limit.
    Cada texto é truncado a 8000 chars (limite seguro para o modelo).
    """
    if not texts:
        return []

    key = _get_openai_key()

    # Limpa e trunca textos
    cleaned = [t[:8000].replace("\n", " ").strip() or " " for t in texts]

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                _OPENAI_API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "input": cleaned,
                    "dimensions": _DIMENSIONS,
                },
            )

        if response.status_code != 200:
            raise Exception(
                f"OpenAI embeddings API error ({response.status_code}): {response.text[:300]}"
            )

        data = response.json()
        # API retorna lista em ordem arbitrária — ordena pelo campo 'index'
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]

    except Exception as e:
        logger.error(f"[EMBEDDING] Falha ao gerar embeddings em batch: {e}")
        raise
