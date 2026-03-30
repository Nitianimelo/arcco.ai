"""
Serviço de preços de modelos LLM.

Busca preços do OpenRouter /api/v1/models e calcula custo estimado em USD
com base no número de tokens prompt + completion.

Cache de 1 hora para evitar chamadas repetidas à API do OpenRouter.
"""

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Cache: model_id → (input_price_per_1m, output_price_per_1m)
_price_cache: dict[str, tuple[float, float]] = {}
_price_cache_ts: float = 0.0
_PRICE_CACHE_TTL = 3600.0  # 1 hora

# Fallback para modelos desconhecidos (preço médio de mercado)
_FALLBACK_INPUT_1M = 1.0
_FALLBACK_OUTPUT_1M = 3.0


async def _refresh_price_cache() -> None:
    """Busca preços do OpenRouter e popula cache interno."""
    global _price_cache, _price_cache_ts

    from backend.core.config import get_config
    config = get_config()

    headers: dict[str, str] = {
        "HTTP-Referer": "https://arcco.ai",
        "X-Title": "Arcco Pricing",
    }
    if config.openrouter_api_key:
        headers["Authorization"] = f"Bearer {config.openrouter_api_key}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if resp.status_code != 200:
                logger.warning("[PRICING] OpenRouter retornou %s ao buscar preços", resp.status_code)
                return
            data = resp.json()
    except Exception as exc:
        logger.warning("[PRICING] Falha ao buscar preços do OpenRouter: %s", exc)
        return

    new_cache: dict[str, tuple[float, float]] = {}
    for m in data.get("data", []):
        model_id = m.get("id", "")
        if not model_id:
            continue
        pricing = m.get("pricing", {})
        try:
            # OpenRouter retorna preço por token; convertemos para por 1M tokens
            input_1m  = float(pricing.get("prompt", 0) or 0) * 1_000_000
            output_1m = float(pricing.get("completion", 0) or 0) * 1_000_000
        except (ValueError, TypeError):
            input_1m = output_1m = 0.0
        new_cache[model_id] = (input_1m, output_1m)

    if new_cache:
        _price_cache = new_cache
        _price_cache_ts = time.time()
        logger.info("[PRICING] Cache de preços atualizado: %d modelos", len(new_cache))


async def get_model_prices(model_id: str) -> tuple[float, float]:
    """
    Retorna (input_price_per_1m, output_price_per_1m) em USD para o modelo.
    Atualiza cache se expirado. Retorna fallback se modelo não encontrado.
    """
    global _price_cache_ts

    now = time.time()
    if not _price_cache or (now - _price_cache_ts) >= _PRICE_CACHE_TTL:
        await _refresh_price_cache()

    # Busca exata
    if model_id in _price_cache:
        return _price_cache[model_id]

    # Busca parcial (ex: "claude-3.5-sonnet" encontra "anthropic/claude-3.5-sonnet")
    for cached_id, prices in _price_cache.items():
        if model_id in cached_id or cached_id in model_id:
            return prices

    logger.debug("[PRICING] Modelo '%s' não encontrado no cache — usando fallback", model_id)
    return (_FALLBACK_INPUT_1M, _FALLBACK_OUTPUT_1M)


async def estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calcula custo estimado em USD.

    Fórmula:
        custo = (prompt_tokens * input_per_1m / 1_000_000)
              + (completion_tokens * output_per_1m / 1_000_000)

    Retorna 0.0 se tokens forem zero.
    """
    if not prompt_tokens and not completion_tokens:
        return 0.0

    input_1m, output_1m = await get_model_prices(model_id)
    cost = (prompt_tokens * input_1m / 1_000_000) + (completion_tokens * output_1m / 1_000_000)
    return round(cost, 8)


def format_cost_usd(cost: float) -> str:
    """Formata custo em USD para exibição legível. Ex: $0.0135"""
    if cost == 0:
        return "$0.00"
    if cost < 0.0001:
        return f"${cost:.6f}"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.4f}"
