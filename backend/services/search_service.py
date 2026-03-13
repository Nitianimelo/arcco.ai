"""
Serviço de busca web — Tavily (primário) + Brave (fallback).
Portado de netlify/functions/search.ts e lib/agent-tools.ts
"""

import logging
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


async def search_tavily(query: str, api_key: str, max_results: int = 5) -> dict:
    """Busca via Tavily API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
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
        response.raise_for_status()
        return response.json()


async def search_brave(query: str, api_key: str, max_results: int = 5) -> dict:
    """Busca via Brave Search API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://api.search.brave.com/res/v1/web/search?q={quote_plus(query)}&count={max_results}",
            headers={"X-Subscription-Token": api_key},
        )
        response.raise_for_status()
        data = response.json()

        # Normalizar formato para compatibilidade
        results = []
        for r in data.get("web", {}).get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("description", ""),
            })

        return {"answer": None, "results": results, "query": query}


async def search_web(
    query: str,
    max_results: int = 5,
    tavily_key: Optional[str] = None,
    brave_key: Optional[str] = None,
) -> dict:
    """
    Busca web com fallback automático.
    Carrega a chave dinamicamente do Supabase (ApiKeys) se não fornecida.
    """
    from backend.core.llm import get_search_key

    if not tavily_key and not brave_key:
        key = await get_search_key()
        if key.startswith("tvly-"):
            tavily_key = key
        elif key:
            brave_key = key

    # Tavily como primário
    if tavily_key:
        try:
            return await search_tavily(query, tavily_key, max_results)
        except Exception as e:
            logger.warning(f"Tavily search failed, trying Brave: {e}")

    # Brave como fallback
    if brave_key:
        try:
            return await search_brave(query, brave_key, max_results)
        except Exception as e:
            logger.error(f"Brave search also failed: {e}")
            raise

    raise ValueError("Nenhuma chave de busca configurada. Adicione 'tavily' ou 'brave' na tabela ApiKeys do Supabase.")


async def search_web_formatted(query: str, api_key: Optional[str] = None) -> str:
    """
    Busca e retorna resultado formatado em markdown.
    Usado pelo agente como tool.
    Carrega a chave dinamicamente do Supabase (ApiKeys) se não fornecida.
    """
    from backend.core.llm import get_search_key

    key = api_key or await get_search_key()
    if not key:
        return "ERRO: Chave de API de busca não configurada. Adicione 'tavily' ou 'brave' na tabela ApiKeys do Supabase."

    try:
        if key.startswith("tvly-"):
            data = await search_tavily(query, key, 10)
            answer = data.get("answer", "")
            results_text = f"**Resumo:** {answer}\n\n**Fontes:**\n"
            for i, r in enumerate(data.get("results", []), 1):
                content = r.get("content", "")[:300]
                results_text += f"[{i}] {r['title']} ({r['url']})\n{content}...\n\n"
            return results_text
        else:
            data = await search_brave(query, key, 5)
            lines = []
            for r in data.get("results", []):
                lines.append(f"• **{r['title']}**\n  {r['url']}\n  {r['content']}")
            return f'**Resultados para "{query}":**\n\n' + "\n\n".join(lines)
    except Exception as e:
        return f"Erro na busca: {e}"
