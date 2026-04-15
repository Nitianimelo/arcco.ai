"""
Serviço de busca de imagens via Unsplash API oficial (v1).

Endpoint: GET https://api.unsplash.com/search/photos
Auth: Client-ID {UNSPLASH_ACCESS_KEY}

Fluxo de enriquecimento de designs:
  1. extract_design_keywords(instruction) → extrai 3-5 keywords em inglês via gpt-4o-mini
  2. search_unsplash_images(keywords)      → busca imagens na API Unsplash
  3. format_images_for_prompt(images)      → bloco formatado para injeção no prompt do design_generator

Fallback gracioso: retorna string/lista vazia se key ausente ou qualquer etapa falhar.
Nunca lança exceção para o orchestrator — todos os erros são capturados internamente.
"""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

# ── Configurações ──────────────────────────────────────────────────────────────
_UNSPLASH_API_BASE = "https://api.unsplash.com"
_SEARCH_TIMEOUT = 10.0   # segundos para chamada Unsplash
_KEYWORD_TIMEOUT = 15.0  # segundos para extração de keywords via LLM
_DEFAULT_COUNT = 5       # imagens por busca


# ── Acesso à key ──────────────────────────────────────────────────────────────

def _get_unsplash_key() -> str:
    """Retorna a Unsplash Access Key via config (env var ou Supabase)."""
    try:
        from backend.core.config import get_config
        return get_config().unsplash_access_key or ""
    except Exception:
        return ""


# ── Extração de keywords ──────────────────────────────────────────────────────

async def extract_design_keywords(instruction: str) -> str:
    """
    Extrai 3-5 keywords de busca em inglês a partir de uma instrução de design.

    Usa gpt-4o-mini via call_openrouter (chamada leve, ~1-2s, barata).
    Retorna string com keywords separadas por vírgulas.
    Retorna string vazia em caso de falha ou instrução vazia.
    """
    if not instruction or not instruction.strip():
        return ""

    try:
        from backend.core.llm import call_openrouter

        prompt = (
            "Extract 3 to 5 concise English search keywords for Unsplash image search, "
            "based on the following design instruction. "
            "Return ONLY a comma-separated list of keywords, nothing else. "
            "Keywords must be in English, specific, and visually descriptive.\n\n"
            f"Design instruction: {instruction[:600]}"
        )

        data = await asyncio.wait_for(
            call_openrouter(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-4o-mini",
                max_tokens=60,
                temperature=0.2,
            ),
            timeout=_KEYWORD_TIMEOUT,
        )
        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            .strip("`")
        )
        logger.debug("[UNSPLASH] Keywords extraídas: %s", raw[:100])
        return raw

    except asyncio.TimeoutError:
        logger.warning("[UNSPLASH] Timeout ao extrair keywords de design.")
        return ""
    except Exception as e:
        logger.warning("[UNSPLASH] Erro ao extrair keywords: %s", e)
        return ""


# ── Busca de imagens ──────────────────────────────────────────────────────────

async def search_unsplash_images(
    query: str,
    *,
    per_page: int = _DEFAULT_COUNT,
    orientation: str = "landscape",
) -> list[dict]:
    """
    Busca imagens no Unsplash via GET /search/photos.

    Retorna lista de dicts:
        [{"url": str, "alt": str}, ...]

    Retorna lista vazia se:
    - UNSPLASH_ACCESS_KEY não configurada
    - query vazia
    - API falhar por qualquer motivo
    """
    if not query or not query.strip():
        return []

    key = _get_unsplash_key()
    if not key:
        logger.debug("[UNSPLASH] Access key ausente — integração desabilitada.")
        return []

    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            response = await client.get(
                f"{_UNSPLASH_API_BASE}/search/photos",
                params={
                    "query": query.strip(),
                    "per_page": per_page,
                    "orientation": orientation,
                },
                headers={
                    "Authorization": f"Client-ID {key}",
                    "Accept-Version": "v1",
                },
            )

        if response.status_code != 200:
            logger.warning(
                "[UNSPLASH] Erro na busca '%s': status=%s",
                query[:50],
                response.status_code,
            )
            return []

        results = response.json().get("results", [])
        images = []
        for item in results:
            urls = item.get("urls", {})
            url = urls.get("regular") or urls.get("full")
            if not url:
                continue
            alt = (
                item.get("alt_description")
                or item.get("description")
                or "image"
            )
            images.append({"url": url, "alt": alt})

        logger.info("[UNSPLASH] Query '%s' → %d imagem(ns).", query[:50], len(images))
        return images

    except asyncio.TimeoutError:
        logger.warning("[UNSPLASH] Timeout na busca '%s'.", query[:50])
        return []
    except Exception as e:
        logger.warning("[UNSPLASH] Erro inesperado na busca '%s': %s", query[:50], e)
        return []


# ── Formatação para prompt ────────────────────────────────────────────────────

def format_images_for_prompt(images: list[dict]) -> str:
    """
    Formata lista de imagens para injeção no prompt do design_generator.
    Inclui sugestão de uso (background/elemento/glass) baseada na posição.
    Retorna string vazia se lista vazia.
    """
    if not images:
        return ""

    # Sugestão de uso por posição: 1a imagem como hero, demais como conteúdo
    uso_hints = [
        "HERO/CAPA — ideal como background full-bleed com overlay gradiente escuro",
        "CONTEÚDO — ideal como background de slide com glass card sobre ela",
        "DETALHE — ideal como imagem lateral em coluna ou bloco bento",
        "ACENTO — ideal como thumbnail, elemento visual ou fundo de seção",
        "ENCERRAMENTO — ideal como background do slide final/conclusão",
    ]

    lines = ["\n\nIMAGENS DISPONÍVEIS — Unsplash (URLs prontas, use exatamente como estão):"]
    for i, img in enumerate(images, start=1):
        hint = uso_hints[min(i - 1, len(uso_hints) - 1)]
        lines.append(f"[IMG{i}] uso sugerido: {hint}")
        lines.append(f"       url: {img['url']}")
        lines.append(f"       alt: {img['alt']}")
    lines.append(
        "\nCOMO USAR:"
        "\n- Background full-bleed: background: url('URL') center/cover — adicione overlay gradiente para legibilidade do texto."
        "\n- Glass card: coloque um .glass-card (backdrop-filter:blur) sobre o slide com background-image."
        "\n- Elemento visual: <img src='URL' style='object-fit:cover;border-radius:16px;width:100%;height:100%'>"
        "\n- NUNCA substitua a URL por placeholder. NUNCA omita border-radius em imagens inline."
        "\n- Distribua: não repita a mesma imagem em slides consecutivos."
    )
    return "\n".join(lines)


# ── Pipeline completo ─────────────────────────────────────────────────────────

async def enrich_design_instruction(instruction: str) -> str:
    """
    Pipeline completo de enriquecimento com imagens Unsplash:
      1. Extrai keywords em inglês da instrução (via gpt-4o-mini)
      2. Busca imagens no Unsplash com as keywords
      3. Retorna bloco formatado para injeção no prompt do design_generator

    Retorna string vazia se:
    - UNSPLASH_ACCESS_KEY não configurada
    - instrução vazia
    - qualquer etapa falhar
    """
    keywords = await extract_design_keywords(instruction)
    if not keywords:
        return ""

    images = await search_unsplash_images(keywords, per_page=_DEFAULT_COUNT)
    return format_images_for_prompt(images)
