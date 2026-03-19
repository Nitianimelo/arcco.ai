"""
Wrapper para chamadas LLM via OpenRouter e Anthropic.
"""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Cache em memória com TTL de 60 segundos.
# Supabase (tabela ApiKeys) é a Única Fonte da Verdade.
# Se a chave for alterada no painel admin, será recarregada no próximo ciclo de TTL.
_api_key_cache: dict = {"key": None, "ts": 0.0}
_search_key_cache: dict = {"key": None, "ts": 0.0}
_vercel_key_cache: dict = {"key": None, "ts": 0.0}
_API_KEY_TTL = 60.0  # segundos


async def get_api_key(force_refresh: bool = False) -> str:
    """
    Busca a API key do Supabase (tabela ApiKeys) — Única Fonte da Verdade.
    Cache de 60s para evitar chamadas excessivas.
    Se force_refresh=True, ignora o cache e recarrega do Supabase.
    """
    global _api_key_cache

    from .config import get_config
    config = get_config()

    now = time.time()
    cache_valid = (
        not force_refresh
        and _api_key_cache["key"]
        and (now - _api_key_cache["ts"]) < _API_KEY_TTL
    )

    if cache_valid:
        return _api_key_cache["key"]

    # Busca sempre do Supabase (Single Source of Truth)
    supabase_url = config.supabase_url
    supabase_key = config.supabase_key

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        url = f"{supabase_url}/rest/v1/ApiKeys?select=api_key&provider=eq.openrouter&is_active=eq.true"
        print("[GET_API_KEY] Querying Supabase (ApiKeys)...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                rows = response.json()
                if rows and rows[0].get("api_key"):
                    key = rows[0]["api_key"]
                    _api_key_cache = {"key": key, "ts": now}
                    config.openrouter_api_key = key
                    print(f"[GET_API_KEY] OK - key loaded: {key[:15]}...")
                    return key
            else:
                print(f"[GET_API_KEY] Supabase retornou status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[GET_API_KEY] ERROR: {e}")

    # Fallback: usar key já em cache (Supabase indisponível temporariamente)
    if _api_key_cache["key"]:
        print("[GET_API_KEY] WARN - Supabase unavailable, using stale cache")
        return _api_key_cache["key"]

    print("[GET_API_KEY] FATAL: No API key found in Supabase!")
    raise ValueError("Chave OpenRouter não encontrada no Supabase (tabela ApiKeys)")


async def get_search_key(force_refresh: bool = False) -> str:
    """
    Busca a API key do Tavily do Supabase (tabela ApiKeys) — Única Fonte da Verdade.
    Cache de 60s para evitar chamadas excessivas.
    """
    global _search_key_cache

    from .config import get_config
    config = get_config()

    now = time.time()
    cache_valid = (
        not force_refresh
        and _search_key_cache["key"]
        and (now - _search_key_cache["ts"]) < _API_KEY_TTL
    )

    if cache_valid:
        return _search_key_cache["key"]

    supabase_url = config.supabase_url
    supabase_key = config.supabase_key
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        url = f"{supabase_url}/rest/v1/ApiKeys?select=api_key&provider=eq.tavily&is_active=eq.true"
        print("[GET_SEARCH_KEY] Querying Supabase: provider=tavily")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            print(f"[GET_SEARCH_KEY] Status: {response.status_code} | Body: {response.text[:200]}")
            if response.status_code == 200:
                rows = response.json()
                if rows and rows[0].get("api_key"):
                    key = rows[0]["api_key"]
                    _search_key_cache = {"key": key, "ts": now}
                    print(f"[GET_SEARCH_KEY] OK - tavily key loaded: {key[:15]}...")
                    return key
                else:
                    print("[GET_SEARCH_KEY] provider=tavily — chave não encontrada na tabela ApiKeys")
            else:
                print(f"[GET_SEARCH_KEY] Supabase retornou status {response.status_code}")
    except Exception as e:
        print(f"[GET_SEARCH_KEY] ERROR: {e}")

    # Fallback: stale cache se Supabase indisponível
    if _search_key_cache["key"]:
        print("[GET_SEARCH_KEY] WARN - usando cache antigo (Supabase indisponível)")
        return _search_key_cache["key"]

    print("[GET_SEARCH_KEY] FATAL: Chave Tavily não encontrada no Supabase (provider='tavily').")
    return ""


async def get_vercel_key(force_refresh: bool = False) -> str:
    """
    Busca a API key do Vercel do Supabase (tabela ApiKeys) — provider='vercel'.
    Cache de 60s para evitar chamadas excessivas.
    """
    global _vercel_key_cache

    from .config import get_config
    config = get_config()

    now = time.time()
    if (
        not force_refresh
        and _vercel_key_cache["key"]
        and (now - _vercel_key_cache["ts"]) < _API_KEY_TTL
    ):
        return _vercel_key_cache["key"]

    supabase_url = config.supabase_url
    supabase_key = config.supabase_key
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        url = f"{supabase_url}/rest/v1/ApiKeys?select=api_key&provider=eq.vercel&is_active=eq.true"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                rows = response.json()
                if rows and rows[0].get("api_key"):
                    key = rows[0]["api_key"]
                    _vercel_key_cache = {"key": key, "ts": now}
                    print(f"[GET_VERCEL_KEY] OK - key loaded: {key[:20]}...")
                    return key
    except Exception as e:
        print(f"[GET_VERCEL_KEY] ERROR: {e}")

    if _vercel_key_cache["key"]:
        print("[GET_VERCEL_KEY] WARN - usando cache antigo (Supabase indisponível)")
        return _vercel_key_cache["key"]

    print("[GET_VERCEL_KEY] Chave Vercel não encontrada no Supabase.")
    return ""


async def call_openrouter(
    messages: list,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    tools: Optional[list] = None,
    tool_choice=None,
) -> dict:
    """
    Chamada ao OpenRouter API.
    Retorna a resposta completa do modelo.
    Se der 401, tenta recarregar a key do Supabase e tentar novamente.
    """
    from .config import get_config
    config = get_config()

    api_key = await get_api_key()
    print(f"[CALL_OPENROUTER] Using API key: {api_key[:15] if api_key else 'EMPTY'}... (len={len(api_key) if api_key else 0})")
    model = model or config.openrouter_model

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    if tools:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://arcco.ai",
                "X-Title": "Arcco.ai Agent",
            },
            json=payload,
        )

        # Se 401, tenta recarregar a key do Supabase e tentar uma vez mais
        if response.status_code == 401:
            print(f"[CALL_OPENROUTER] 401 with key {api_key[:15]}... - trying to refresh key from Supabase")
            try:
                new_key = await get_api_key(force_refresh=True)
                if new_key and new_key != api_key:
                    print(f"[CALL_OPENROUTER] Retrying with new key: {new_key[:15]}...")
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {new_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://arcco.ai",
                            "X-Title": "Arcco.ai Agent",
                        },
                        json=payload,
                    )
            except Exception as e:
                print(f"[CALL_OPENROUTER] Key refresh failed: {e}")

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"OpenRouter error ({response.status_code}): {error_text}")
            raise Exception(f"LLM API Error: {error_text}")

        return response.json()

async def stream_openrouter(
    messages: list,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    tools: Optional[list] = None,
):
    """
    Chamada ao OpenRouter API com Streaming (Server-Sent Events).
    Gera chunks de resposta à medida que são recebidos.
    """
    from .config import get_config
    config = get_config()

    api_key = await get_api_key()
    model = model or config.openrouter_model

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://arcco.ai",
            "X-Title": "Arcco.ai Agent",
        }
        request = client.build_request(
            "POST",
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response = await client.send(request, stream=True)

        # Se 401, tenta recarregar a key do Supabase e tentar uma vez mais
        if response.status_code == 401:
            await response.aclose()
            print(f"[STREAM_OPENROUTER] 401 with key {api_key[:15]}... - trying to refresh key")
            try:
                new_key = await get_api_key(force_refresh=True)
                if new_key and new_key != api_key:
                    print(f"[STREAM_OPENROUTER] Retrying with new key: {new_key[:15]}...")
                    headers["Authorization"] = f"Bearer {new_key}"
                    request = client.build_request(
                        "POST",
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response = await client.send(request, stream=True)
            except Exception as e:
                print(f"[STREAM_OPENROUTER] Key refresh failed: {e}")

        if response.status_code != 200:
            error_text = await response.aread()
            logger.error(f"OpenRouter stream error ({response.status_code}): {error_text}")
            raise Exception(f"LLM Stream API Error: {error_text}")

        import json
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    pass
