"""
Wrapper para chamadas LLM via OpenRouter e Anthropic.
"""

import logging
import re
import time
from contextvars import ContextVar
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Token Tracking (ContextVar — isolado por request async) ──────────────────
# Cada request FastAPI/SSE tem seu próprio contexto assíncrono.
# call_openrouter e stream_openrouter acumulam automaticamente neste dict.

_token_accumulator: ContextVar[dict | None] = ContextVar("token_accumulator", default=None)


def start_token_tracking() -> dict:
    """
    Inicia acumulação de tokens para a request atual.
    Deve ser chamado no início de cada request SSE em chat.py.
    Retorna o dict de acumulação (pode ser lido depois via get_token_usage()).
    """
    acc: dict = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        # Campos específicos do stream (preenchidos pelo último chunk de usage)
        "stream_prompt_tokens": 0,
        "stream_completion_tokens": 0,
        "stream_total_tokens": 0,
    }
    _token_accumulator.set(acc)
    return acc


def get_token_usage() -> dict:
    """
    Retorna os tokens acumulados na request atual.
    Prioriza os valores de stream (mais precisos) sobre os acumulados de call_openrouter.
    """
    acc = _token_accumulator.get()
    if not acc:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    # Se o stream capturou usage, esses valores são os mais confiáveis para o modo agente
    # (incluem todos os tokens da última chamada streaming do supervisor)
    # Para chat normal, stream_* é o único valor preenchido
    return acc


# Regex para remover blocos <think>...</think> de modelos de reasoning
# (DeepSeek R1, QwQ, Marco-o1, etc. jogam tokens de pensamento no content)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _normalize_message(message: dict) -> dict:
    """
    Normaliza a mensagem de resposta do LLM para formato consistente.

    - Remove blocos <think>...</think> que modelos de reasoning emitem no content
      (DeepSeek R1, QwQ, Marco-o1, etc.)
    - O campo reasoning_content (DeepSeek R1 nativo) é preservado intacto —
      ele fica separado do content e não interfere no pipeline
    - Garante que content nunca seja None (usa string vazia como fallback)
    """
    content = message.get("content") or ""

    if "<think>" in content:
        cleaned = _THINK_RE.sub("", content).strip()
        if cleaned != content:
            logger.debug("[LLM] Blocos <think> removidos do content (%d chars → %d chars)", len(content), len(cleaned))
        message["content"] = cleaned

    return message

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

        data = response.json()
        # Normaliza a mensagem de cada choice (remove thinking tokens, etc.)
        for choice in data.get("choices", []):
            if isinstance(choice.get("message"), dict):
                _normalize_message(choice["message"])

        # Acumula tokens no ContextVar da request atual (se tracking ativo)
        _acc = _token_accumulator.get()
        if _acc is not None:
            _usage = data.get("usage") or {}
            _acc["prompt_tokens"]     += int(_usage.get("prompt_tokens", 0) or 0)
            _acc["completion_tokens"] += int(_usage.get("completion_tokens", 0) or 0)
            _acc["total_tokens"]      += int(_usage.get("total_tokens", 0) or 0)

        return data

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
        "stream_options": {"include_usage": True},  # OpenRouter envia usage no último chunk
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
                    parsed = json.loads(data_str)
                    # Captura o bloco de usage do último chunk (stream_options: include_usage)
                    # OpenRouter envia usage no chunk com choices[0].finish_reason = "stop"
                    _s_acc = _token_accumulator.get()
                    if _s_acc is not None and parsed.get("usage"):
                        _s_usage = parsed["usage"]
                        # Usa set (não +=) pois este é o total acumulado do stream inteiro
                        _s_acc["stream_prompt_tokens"]     = int(_s_usage.get("prompt_tokens", 0) or 0)
                        _s_acc["stream_completion_tokens"] = int(_s_usage.get("completion_tokens", 0) or 0)
                        _s_acc["stream_total_tokens"]      = int(_s_usage.get("total_tokens", 0) or 0)
                    yield parsed
                except json.JSONDecodeError:
                    pass
