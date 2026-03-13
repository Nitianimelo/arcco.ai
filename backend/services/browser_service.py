"""
Serviço de navegação remota via Browserbase + Playwright (CDP).

Substitui o Firecrawl como motor do ask_browser. A sessão roda nos
servidores do Browserbase (Stealth Mode, zero RAM local). A interface
de actions permanece idêntica para o LLM.

Variáveis de ambiente necessárias:
    BROWSERBASE_API_KEY      — chave da conta Browserbase
    BROWSERBASE_PROJECT_ID   — ID do projeto Browserbase

Tipos de action suportados (mesma interface de tools.py):
    click | write | scroll | wait | press | execute_javascript | screenshot | scrape

NOTA WINDOWS: usa playwright.sync_api em asyncio.to_thread para evitar
o NotImplementedError do asyncio.create_subprocess_exec no Windows/uvicorn.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 15_000

_NOISE_TAGS = [
    "script", "style", "noscript", "nav", "footer",
    "header", "aside", "form", "svg", "meta", "link",
]


# ── Entrypoint Público ─────────────────────────────────────────────────────────

async def execute_browserbase_task(
    url: str,
    actions: list[dict[str, Any]] | None = None,
    wait_for: int = 0,
    mobile: bool = False,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> str:
    """
    Cria uma sessão Browserbase, conecta via CDP com Playwright (sync API em thread),
    executa as actions e retorna o conteúdo extraído como texto.
    """
    from backend.core.config import get_config
    config = get_config()

    api_key = config.browserbase_api_key
    project_id = config.browserbase_project_id

    if not api_key:
        return (
            "Erro: Browserbase API key não configurada. "
            "Adicione na tabela ApiKeys do Supabase: "
            "provider='browserbase', api_key='bb_live_...'."
        )
    if not project_id:
        return (
            "Erro: Browserbase Project ID não configurado. "
            "Adicione na tabela ApiKeys do Supabase: "
            "provider='browserbase_project_id', api_key='<uuid>'."
        )

    try:
        from browserbase import Browserbase
    except ImportError as exc:
        return (
            f"Erro de dependência: {exc}. "
            "Execute: pip install browserbase playwright && playwright install chromium"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return (
            f"Erro de dependência: {exc}. "
            "Execute: pip install playwright && playwright install chromium"
        )

    actions = actions or []
    bb = Browserbase(api_key=api_key)

    # Cria a sessão Browserbase (SDK síncrono)
    try:
        session = await asyncio.to_thread(
            lambda: bb.sessions.create(project_id=project_id)
        )
        logger.info(f"[BROWSER] Sessão criada: {session.id} → {url}")
    except Exception as exc:
        logger.error(f"[BROWSER] Falha ao criar sessão Browserbase: {exc}")
        return f"Erro ao criar sessão no Browserbase: {exc}"

    # Executa toda a navegação em uma thread (sync_playwright não precisa de subprocess asyncio)
    result = await asyncio.to_thread(
        _run_sync_session,
        session.connect_url,
        session.id,
        url,
        actions,
        wait_for,
        mobile,
        include_tags,
        exclude_tags,
    )

    # Libera a sessão
    try:
        await asyncio.to_thread(
            lambda: bb.sessions.update(session.id, status="REQUEST_RELEASE")
        )
        logger.info(f"[BROWSER] Sessão {session.id} liberada.")
    except Exception as exc:
        logger.warning(f"[BROWSER] Falha ao liberar sessão {session.id}: {exc}")

    return result


# ── Execução Síncrona (roda em thread) ────────────────────────────────────────

def _run_sync_session(
    connect_url: str,
    session_id: str,
    url: str,
    actions: list[dict[str, Any]],
    wait_for: int,
    mobile: bool,
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> str:
    """
    Lógica completa de navegação usando a API SÍNCRONA do Playwright.
    Chamada via asyncio.to_thread para não bloquear o event loop.
    """
    from playwright.sync_api import sync_playwright

    scraped_content = ""
    action_log: list[str] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(
                connect_url,
                timeout=30_000,
            )

            if browser.contexts:
                context = browser.contexts[0]
            else:
                context_opts: dict[str, Any] = {}
                if mobile:
                    context_opts["viewport"] = {"width": 390, "height": 844}
                    context_opts["user_agent"] = (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                        "Version/17.0 Mobile/15E148 Safari/604.1"
                    )
                context = browser.new_context(**context_opts)

            page = context.pages[0] if context.pages else context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                logger.info(f"[BROWSER] Página carregada: {page.title()!r}")
            except Exception as exc:
                logger.error(f"[BROWSER] Erro ao navegar para {url}: {exc}")
                return f"Erro ao carregar a página {url}: {exc}"

            if wait_for > 0:
                page.wait_for_timeout(wait_for)

            # ── Executar actions ───────────────────────────────────────────
            for action in actions:
                action_type = action.get("type", "")
                try:
                    if action_type == "click":
                        selector = action["selector"]
                        page.click(selector, timeout=10_000)
                        action_log.append(f"click({selector!r})")

                    elif action_type == "write":
                        selector = action["selector"]
                        text = action.get("text", "")
                        page.fill(selector, text, timeout=10_000)
                        action_log.append(f"write({selector!r}, {text!r})")

                    elif action_type == "scroll":
                        direction = action.get("direction", "down")
                        amount = int(action.get("amount", 500))
                        delta = amount if direction == "down" else -amount
                        page.evaluate(f"window.scrollBy(0, {delta})")
                        action_log.append(f"scroll({direction}, {amount}px)")

                    elif action_type == "wait":
                        ms = max(0, int(action.get("milliseconds", 1_000)))
                        page.wait_for_timeout(ms)
                        action_log.append(f"wait({ms}ms)")

                    elif action_type == "press":
                        key = action.get("key", "Enter")
                        selector = action.get("selector")
                        if selector:
                            page.press(selector, key, timeout=10_000)
                        else:
                            page.keyboard.press(key)
                        action_log.append(f"press({key!r})")

                    elif action_type == "execute_javascript":
                        script = action.get("script", "")
                        result = page.evaluate(script)
                        action_log.append(f"js() → {str(result)[:80]!r}")

                    elif action_type == "screenshot":
                        screenshot_note = _try_screenshot_sync(page)
                        action_log.append(f"screenshot({screenshot_note})")

                    elif action_type == "scrape":
                        intermediate = _extract_page_text_sync(page, include_tags, exclude_tags)
                        scraped_content = intermediate
                        action_log.append(f"scrape(intermediário, {len(intermediate)} chars)")

                    else:
                        logger.warning(f"[BROWSER] Action desconhecida: {action_type!r}")
                        action_log.append(f"⚠️ desconhecida({action_type!r})")

                except KeyError as exc:
                    logger.warning(f"[BROWSER] Parâmetro ausente na action '{action_type}': {exc}")
                    action_log.append(f"❌ {action_type}(param faltando: {exc})")
                except Exception as exc:
                    logger.warning(f"[BROWSER] Falha na action '{action_type}': {exc}")
                    action_log.append(f"❌ {action_type} → {str(exc)[:60]}")

            # ── Scrape final ───────────────────────────────────────────────
            final_content = _extract_page_text_sync(page, include_tags, exclude_tags)
            if final_content:
                scraped_content = final_content

            page_title = page.title()
            browser.close()

    except Exception as exc:
        logger.error(f"[BROWSER] Erro crítico na sessão {session_id}: {exc}")
        return f"Erro durante navegação com Browserbase: {exc}"

    # ── Montar resposta final ──────────────────────────────────────────────────
    if not scraped_content:
        scraped_content = f"Página acessada ({page_title!r}), mas nenhum conteúdo extraível foi encontrado."

    if len(scraped_content) > _MAX_CONTENT_CHARS:
        scraped_content = (
            scraped_content[:_MAX_CONTENT_CHARS]
            + "\n\n... [Truncado por limite de tokens]"
        )

    actions_summary = (
        f"\nAções executadas: {', '.join(action_log)}" if action_log else ""
    )
    return f"Conteúdo extraído de {url}{actions_summary}:\n\n{scraped_content}"


# ── Helpers Síncronos ──────────────────────────────────────────────────────────

def _extract_page_text_sync(
    page: Any,
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> str:
    try:
        from bs4 import BeautifulSoup

        raw_html = page.content()
        soup = BeautifulSoup(raw_html, "html.parser")

        for tag in soup(_NOISE_TAGS + (exclude_tags or [])):
            tag.decompose()

        if include_tags:
            elements = soup.find_all(include_tags)
            if elements:
                return "\n\n".join(
                    el.get_text(separator=" ", strip=True) for el in elements
                )

        return soup.get_text(separator=" ", strip=True)

    except Exception as exc:
        logger.error(f"[BROWSER] Falha na extração de texto: {exc}")
        return ""


def _try_screenshot_sync(page: Any) -> str:
    try:
        screenshot_bytes: bytes = page.screenshot(full_page=False)
        try:
            import time
            from backend.core.config import get_config
            from backend.core.supabase_client import upload_to_supabase

            config = get_config()
            filename = f"screenshot-{int(time.time())}.png"
            url = upload_to_supabase(
                config.supabase_storage_bucket,
                filename,
                screenshot_bytes,
                "image/png",
            )
            return f"URL: {url}"
        except Exception:
            return "✓ (sem upload)"
    except Exception as exc:
        return f"falhou: {str(exc)[:40]}"
