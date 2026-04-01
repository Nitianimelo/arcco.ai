import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Cache: model_id → (input_price_per_1m, output_price_per_1m)
_price_cache: dict[str, tuple[float, float]] = {}
_price_cache_ts: float = 0.0
_PRICE_CACHE_TTL = 3600.0  # 1 hora
_FAILED_CACHE_TTL = 300.0  # 5 minutos de espera antes de retentar falhas

# Evita thundering herd quando vários chats fecham ao mesmo tempo.
_price_lock = asyncio.Lock()

# Fallback para modelos desconhecidos ou indisponibilidade da API
_FALLBACK_INPUT_1M = 1.0
_FALLBACK_OUTPUT_1M = 3.0


def _mark_refresh_failure() -> None:
    global _price_cache_ts
    # Reaproveita a mesma lógica de expiração: o cache "parece" ter sido
    # atualizado há PRICE_CACHE_TTL - FAILED_CACHE_TTL segundos.
    _price_cache_ts = time.time() - _PRICE_CACHE_TTL + _FAILED_CACHE_TTL


async def _refresh_price_cache() -> None:
    """Busca preços do OpenRouter e popula cache interno com proteção contra falhas."""
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
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if resp.status_code != 200:
                logger.warning(
                    "[PRICING] OpenRouter retornou %s. Aplicando negative cache.",
                    resp.status_code,
                )
                _mark_refresh_failure()
                return
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "[PRICING] Falha de rede ao buscar preços: %s. Aplicando negative cache.",
            exc,
        )
        _mark_refresh_failure()
        return

    if not isinstance(data, dict):
        logger.warning("[PRICING] Payload inválido da OpenRouter. Aplicando negative cache.")
        _mark_refresh_failure()
        return

    new_cache: dict[str, tuple[float, float]] = {}
    for model_data in data.get("data", []):
        model_id = model_data.get("id", "")
        if not model_id:
            continue

        pricing = model_data.get("pricing", {})
        try:
            input_1m = float(pricing.get("prompt", 0) or 0) * 1_000_000
            output_1m = float(pricing.get("completion", 0) or 0) * 1_000_000
        except (ValueError, TypeError):
            input_1m = output_1m = 0.0

        new_cache[model_id] = (input_1m, output_1m)

    if new_cache:
        _price_cache = new_cache
        _price_cache_ts = time.time()
        logger.info("[PRICING] Cache de preços atualizada: %d modelos carregados", len(new_cache))
        return

    logger.warning("[PRICING] OpenRouter não retornou modelos válidos. Aplicando negative cache.")
    _mark_refresh_failure()


async def get_model_prices(model_id: str) -> tuple[float, float]:
    """Retorna preços em USD e lida com concorrência assíncrona dos chats."""
    now = time.time()

    if not _price_cache or (now - _price_cache_ts) >= _PRICE_CACHE_TTL:
        async with _price_lock:
            now = time.time()
            if not _price_cache or (now - _price_cache_ts) >= _PRICE_CACHE_TTL:
                await _refresh_price_cache()

    if model_id in _price_cache:
        return _price_cache[model_id]

    for cached_id, prices in _price_cache.items():
        if model_id in cached_id or cached_id in model_id:
            return prices

    logger.debug("[PRICING] Modelo '%s' não encontrado no cache — usando fallback", model_id)
    return (_FALLBACK_INPUT_1M, _FALLBACK_OUTPUT_1M)


async def estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    if not prompt_tokens and not completion_tokens:
        return 0.0

    input_1m, output_1m = await get_model_prices(model_id)
    cost = (prompt_tokens * input_1m / 1_000_000) + (completion_tokens * output_1m / 1_000_000)
    return round(cost, 8)


def format_cost_usd(cost: float) -> str:
    if cost == 0:
        return "$0.00"
    if cost < 0.0001:
        return f"${cost:.6f}"
    return f"${cost:.4f}"
