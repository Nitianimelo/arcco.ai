"""
Motor de Pesquisa Profunda (Deep Research) do Arcco.

Executa pesquisas multi-etapa complexas com 4 fases:
  1. Planejamento — LLM gera queries de busca + pontos de dados necessários
  2. Descoberta  — Buscas paralelas via Tavily
  3. Coleta      — Navegação paralela via Browserbase com sumarização imediata
  4. Síntese     — LLM gera relatório estruturado final

Projetado para pesquisas de mercado, análise competitiva, levantamento de dados
e qualquer tarefa que exija visitar múltiplos sites e cruzar informações.
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from backend.core.llm import call_openrouter

logger = logging.getLogger(__name__)

# ── Configuração (valores default, sobrescritos por config.py) ────────────────

def _get_research_config():
    from backend.core.config import get_config
    config = get_config()
    return {
        "max_pages": config.deep_research_max_pages,
        "concurrency": config.deep_research_browser_concurrency,
        "timeout": config.deep_research_timeout,
    }


# ── Helpers SSE ───────────────────────────────────────────────────────────────

def _sse(event_type: str, content: str) -> str:
    return f'data: {{"type": "{event_type}", "content": {json.dumps(content)}}}\n\n'


# ── Fase 1: Planejamento ─────────────────────────────────────────────────────

_PLANNING_PROMPT = """Você é um planejador de pesquisa. Dado o pedido do usuário, gere um plano de pesquisa em JSON PURO (sem markdown).

O JSON deve ter exatamente este formato:
{
  "objective": "Objetivo claro da pesquisa em 1 frase",
  "search_queries": ["query1", "query2", "query3", "query4", "query5"],
  "data_points": ["dado específico 1", "dado específico 2", "dado específico 3"],
  "priority_domains": ["dominio1.com", "dominio2.com"]
}

REGRAS:
- Gere entre 3 e 6 search_queries otimizadas (adicione "2026" para dados recentes)
- data_points: lista do que PRECISA ser encontrado (preços, endereços, avaliações, etc.)
- priority_domains: domínios que provavelmente têm os dados (Google Maps, Instagram, sites locais)
- Responda APENAS com o JSON, sem explicações."""


async def _plan_research(user_query: str, model: str) -> dict:
    """Fase 1: LLM gera plano de pesquisa estruturado."""
    try:
        data = await call_openrouter(
            messages=[
                {"role": "system", "content": _PLANNING_PROMPT},
                {"role": "user", "content": user_query},
            ],
            model=model,
            max_tokens=1000,
            temperature=0.3,
        )
        raw = data["choices"][0]["message"]["content"].strip()
        # Limpa possíveis blocos markdown
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"[DEEP_RESEARCH] Falha no planejamento: {e}")
        # Fallback: plano mínimo
        return {
            "objective": user_query,
            "search_queries": [user_query, f"{user_query} 2026"],
            "data_points": [],
            "priority_domains": [],
        }


# ── Fase 2: Descoberta (Buscas Paralelas) ────────────────────────────────────

async def _discover(queries: list[str]) -> list[dict]:
    """Fase 2: Executa buscas Tavily em paralelo. Retorna lista de resultados."""
    from backend.services.search_service import search_web

    async def _single_search(query: str) -> dict:
        try:
            result = await search_web(query, max_results=5)
            return {"query": query, "results": result.get("results", []), "answer": result.get("answer", "")}
        except Exception as e:
            logger.warning(f"[DEEP_RESEARCH] Busca falhou para '{query}': {e}")
            return {"query": query, "results": [], "answer": ""}

    tasks = [_single_search(q) for q in queries]
    return await asyncio.gather(*tasks)


def _extract_urls_from_discovery(discovery_results: list[dict], priority_domains: list[str], max_urls: int) -> list[dict]:
    """Extrai URLs únicas dos resultados de busca, priorizando domínios relevantes."""
    seen = set()
    priority_urls = []
    other_urls = []

    for search_result in discovery_results:
        for r in search_result.get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")
            if not url or url in seen:
                continue
            seen.add(url)

            # Pular URLs inúteis
            skip_domains = ["youtube.com", "facebook.com", "twitter.com", "x.com", "tiktok.com"]
            if any(d in url.lower() for d in skip_domains):
                continue

            entry = {"url": url, "title": title}
            is_priority = any(d.lower() in url.lower() for d in priority_domains)
            if is_priority:
                priority_urls.append(entry)
            else:
                other_urls.append(entry)

    combined = priority_urls + other_urls
    return combined[:max_urls]


# ── Fase 3: Coleta (Browser Paralelo + Sumarização) ──────────────────────────

_SUMMARIZE_PROMPT = """Você é um extrator de dados. Dado o conteúdo bruto de uma página web e os pontos de dados que preciso, extraia APENAS as informações relevantes.

PONTOS DE DADOS NECESSÁRIOS:
{data_points}

REGRAS:
- Extraia dados concretos: nomes, endereços, preços, telefones, avaliações, horários.
- Se o conteúdo não tiver dados relevantes, responda "SEM_DADOS_RELEVANTES".
- Seja conciso — máximo 500 palavras.
- NÃO invente dados. Extraia apenas o que está no texto."""


async def _fetch_and_summarize(
    url_info: dict,
    data_points: list[str],
    model: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Navega uma URL via Browserbase, extrai conteúdo e sumariza imediatamente."""
    url = url_info["url"]
    title = url_info.get("title", url)

    async with semaphore:
        # Tenta primeiro com web_fetch (rápido, sem JS)
        from backend.agents.executor import execute_tool

        content = await execute_tool("web_fetch", {"url": url})

        # Se o conteúdo for muito curto, tenta com Browserbase
        if len(content) < 200 or "Erro" in content[:50]:
            try:
                content = await execute_tool("ask_browser", {"url": url})
            except Exception as e:
                logger.warning(f"[DEEP_RESEARCH] Browser falhou para {url}: {e}")
                return {"url": url, "title": title, "summary": f"Erro ao acessar: {e}", "success": False}

        # Sumarização imediata para não estourar contexto
        if len(content) > 500 and data_points:
            try:
                summary_prompt = _SUMMARIZE_PROMPT.format(
                    data_points="\n".join(f"- {dp}" for dp in data_points)
                )
                summary_model = model
                data = await call_openrouter(
                    messages=[
                        {"role": "system", "content": summary_prompt},
                        {"role": "user", "content": f"URL: {url}\nTítulo: {title}\n\nConteúdo:\n{content[:8000]}"},
                    ],
                    model=summary_model,
                    max_tokens=800,
                    temperature=0.1,
                )
                summary = data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"[DEEP_RESEARCH] Sumarização falhou para {url}: {e}")
                summary = content[:2000]
        else:
            summary = content[:2000]

        is_relevant = "SEM_DADOS_RELEVANTES" not in summary
        return {"url": url, "title": title, "summary": summary, "success": is_relevant}


# ── Fase 4: Síntese ──────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = """Você é o Arcco, assistente de IA criado por Nitianí Melo.
Você recebeu dados de uma pesquisa profunda. Sintetize tudo em um relatório estruturado e completo.

OBJETIVO DA PESQUISA: {objective}

DADOS COLETADOS DAS BUSCAS:
{search_summaries}

DADOS COLETADOS DOS SITES VISITADOS:
{page_summaries}

REGRAS DE SÍNTESE:
- Organize por tópicos/categorias relevantes.
- Inclua TODOS os dados concretos encontrados (nomes, preços, endereços, avaliações).
- Cite as fontes com links Markdown: [Nome](URL).
- Se dados conflitantes, apresente ambas as versões.
- Conclua com insights e recomendações práticas.
- Responda em Português do Brasil, profissional e direto.
- NÃO invente dados — use APENAS o que foi encontrado nas fontes."""


async def _synthesize(
    objective: str,
    discovery_results: list[dict],
    page_results: list[dict],
    model: str,
) -> str:
    """Fase 4: LLM sintetiza todos os dados em relatório final."""
    # Monta resumo das buscas
    search_lines = []
    for sr in discovery_results:
        if sr.get("answer"):
            search_lines.append(f"**Busca: {sr['query']}**\nResumo: {sr['answer']}")
        for r in sr.get("results", [])[:3]:
            search_lines.append(f"- [{r.get('title', '')}]({r.get('url', '')}): {r.get('content', '')[:200]}")

    # Monta resumo das páginas visitadas
    page_lines = []
    for pr in page_results:
        if pr.get("success"):
            page_lines.append(f"### [{pr['title']}]({pr['url']})\n{pr['summary']}")

    synthesis_prompt = _SYNTHESIS_PROMPT.format(
        objective=objective,
        search_summaries="\n".join(search_lines) if search_lines else "(nenhum resultado de busca)",
        page_summaries="\n\n".join(page_lines) if page_lines else "(nenhuma página visitada com sucesso)",
    )

    try:
        data = await call_openrouter(
            messages=[
                {"role": "system", "content": synthesis_prompt},
                {"role": "user", "content": f"Gere o relatório completo sobre: {objective}"},
            ],
            model=model,
            max_tokens=4096,
            temperature=0.4,
        )
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[DEEP_RESEARCH] Síntese falhou: {e}")
        # Fallback: retorna dados brutos organizados
        fallback = f"# Pesquisa: {objective}\n\n"
        fallback += "## Resultados das Buscas\n" + "\n".join(search_lines[:20]) + "\n\n"
        fallback += "## Dados dos Sites\n" + "\n\n".join(page_lines[:10])
        return fallback


# ── Pipeline Principal ────────────────────────────────────────────────────────

async def run_deep_research(
    query: str,
    model: str,
    context: str = "",
) -> AsyncGenerator[str, None]:
    """
    Executa pesquisa profunda em 4 fases com SSE progress.
    Yields SSE events e finaliza com 'RESULT:' contendo o relatório.
    """
    start_time = time.time()
    rc = _get_research_config()

    # ── Fase 1: Planejamento ──────────────────────────────────────────
    yield _sse("steps", "<step>Planejando estratégia de pesquisa...</step>")

    plan = await _plan_research(f"{query}\n\nContexto adicional: {context}" if context else query, model)
    objective = plan.get("objective", query)
    queries = plan.get("search_queries", [query])
    data_points = plan.get("data_points", [])
    priority_domains = plan.get("priority_domains", [])

    logger.info(f"[DEEP_RESEARCH] Plano: {len(queries)} queries, {len(data_points)} data points")
    yield _sse("thought", f"Plano de pesquisa:\n- Objetivo: {objective}\n- {len(queries)} buscas planejadas\n- Dados-alvo: {', '.join(data_points[:5])}")

    # ── Fase 2: Descoberta ────────────────────────────────────────────
    yield _sse("steps", f"<step>Executando {len(queries)} buscas em paralelo...</step>")

    discovery_results = await _discover(queries)

    total_results = sum(len(sr.get("results", [])) for sr in discovery_results)
    logger.info(f"[DEEP_RESEARCH] Descoberta: {total_results} resultados encontrados")
    yield _sse("steps", f"<step>{total_results} resultados encontrados — selecionando páginas para análise...</step>")

    # Timeout check
    elapsed = time.time() - start_time
    if elapsed > rc["timeout"]:
        yield _sse("steps", "<step>Timeout — sintetizando com dados disponíveis...</step>")
        report = await _synthesize(objective, discovery_results, [], model)
        yield f"RESULT:{report}"
        return

    # ── Fase 3: Coleta ────────────────────────────────────────────────
    urls_to_visit = _extract_urls_from_discovery(discovery_results, priority_domains, rc["max_pages"])

    if urls_to_visit:
        yield _sse("steps", f"<step>Visitando {len(urls_to_visit)} sites para coleta detalhada...</step>")

        semaphore = asyncio.Semaphore(rc["concurrency"])
        page_tasks = [
            _fetch_and_summarize(url_info, data_points, model, semaphore)
            for url_info in urls_to_visit
        ]

        page_results = []
        # Processa em batches para dar feedback
        for i, coro in enumerate(asyncio.as_completed(page_tasks)):
            result = await coro
            page_results.append(result)

            status = "✓" if result.get("success") else "✗"
            yield _sse("steps", f"<step>{status} [{i+1}/{len(urls_to_visit)}] {result['title'][:50]}...</step>")

            # Timeout check
            if time.time() - start_time > rc["timeout"]:
                yield _sse("steps", "<step>Timeout — sintetizando com dados parciais...</step>")
                break
    else:
        page_results = []
        yield _sse("steps", "<step>Nenhuma URL relevante para visitar — sintetizando buscas...</step>")

    # ── Fase 4: Síntese ──────────────────────────────────────────────
    yield _sse("steps", "<step>Sintetizando relatório final com todos os dados coletados...</step>")

    report = await _synthesize(objective, discovery_results, page_results, model)

    elapsed_total = time.time() - start_time
    logger.info(f"[DEEP_RESEARCH] Concluído em {elapsed_total:.1f}s — {len(page_results)} páginas analisadas")
    yield _sse("thought", f"Pesquisa concluída em {elapsed_total:.0f}s: {len(queries)} buscas, {len(page_results)} páginas visitadas")

    yield f"RESULT:{report}"
