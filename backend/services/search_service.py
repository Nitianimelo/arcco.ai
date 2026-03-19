"""
Serviço de busca web — Tavily.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def search_tavily(query: str, api_key: str, max_results: int = 5) -> dict:
    """Busca via Tavily API."""
    logger.info(f"[TAVILY] Iniciando busca: {query[:60]}...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": max_results,
            },
        )
        logger.info(f"[TAVILY] Resposta: status={response.status_code}")
        response.raise_for_status()
        return response.json()


async def search_web(
    query: str,
    max_results: int = 5,
    tavily_key: Optional[str] = None,
) -> dict:
    """
    Busca web via Tavily.
    Carrega a chave dinamicamente do Supabase (ApiKeys) se não fornecida.
    """
    from backend.core.llm import get_search_key

    if not tavily_key:
        key = await get_search_key()
        if key:
            tavily_key = key

    if tavily_key:
        return await search_tavily(query, tavily_key, max_results)

    raise ValueError("Chave de busca Tavily não configurada. Adicione provider='tavily' na tabela ApiKeys do Supabase.")


async def search_web_formatted(query: str, api_key: Optional[str] = None) -> str:
    """
    Busca e retorna resultado formatado em markdown.
    Usado pelo agente como tool.
    Carrega a chave dinamicamente do Supabase (ApiKeys) se não fornecida.
    Timeout interno de 15s para a busca.
    """
    from backend.core.llm import get_search_key

    try:
        key = api_key or await asyncio.wait_for(get_search_key(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.error("[SEARCH] Timeout de 10s ao buscar chave de busca no Supabase")
        return "ERRO: Timeout ao buscar chave de API de busca. Verifique a conexão com o Supabase."
    except Exception as e:
        logger.error(f"[SEARCH] Erro ao buscar chave de busca: {e}")
        return f"ERRO: Falha ao buscar chave de busca: {e}"

    if not key:
        return "ERRO: Chave Tavily não configurada. Adicione provider='tavily' na tabela ApiKeys do Supabase."

    try:
        data = await asyncio.wait_for(
            search_tavily(query, key, 10),
            timeout=15.0,
        )
        answer = data.get("answer", "")
        results_text = f"**Resumo:** {answer}\n\n**Fontes:**\n"
        for i, r in enumerate(data.get("results", []), 1):
            content = r.get("content", "")[:300]
            results_text += f"[{i}] {r['title']} ({r['url']})\n{content}...\n\n"
        return results_text
    except asyncio.TimeoutError:
        logger.error(f"[SEARCH] Timeout de 15s na busca Tavily: {query[:60]}")
        return f"Erro: Timeout de 15s na pesquisa web. O Tavily está lento ou indisponível."
    except Exception as e:
        logger.error(f"[SEARCH] Erro na busca '{query[:60]}': {e}")
        return f"Erro na busca: {e}"
