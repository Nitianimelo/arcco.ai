"""
Serviço de navegação remota via Steel + Playwright (CDP).

Arquitetura:
- Steel fornece a sessão remota do navegador;
- o backend opera em loop iterativo de percepção -> decisão -> ação;
- pop-ups/cookies comuns são tratados antes de gastar tokens;
- captchas e bloqueios geram handoff explícito para o usuário.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import httpx


logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 15_000
_BROWSER_MAX_STEPS = 10
_BROWSER_LOOP_TIMEOUT_SECONDS = 150.0
_BROWSER_RESUME_TTL_SECONDS = 15 * 60.0
_BROWSER_VISIBLE_TEXT_CHARS = 3_500
_BROWSER_MAX_INTERACTIVE_ITEMS = 28
_BROWSER_NAVIGATION_TIMEOUT_MS = 45_000
_BROWSER_ACTION_TIMEOUT_MS = 6_000

_NOISE_TAGS = [
    "script", "style", "noscript", "nav", "footer",
    "header", "aside", "svg", "meta", "link",
]

_COOKIE_KEYWORDS = [
    "accept all",
    "accept",
    "allow all",
    "agree",
    "concordo",
    "aceitar",
    "aceitar cookies",
    "allow cookies",
    "ok",
    "entendi",
    "fechar",
    "close",
    "continuar",
]

_CLOSE_KEYWORDS = [
    "close",
    "fechar",
    "dismiss",
    "skip",
    "agora não",
    "not now",
    "talvez depois",
    "cancelar",
    "cancel",
]

_HUMAN_GATE_PATTERNS = [
    "captcha",
    "hcaptcha",
    "recaptcha",
    "verifique se é humano",
    "verifique que é humano",
    "confirme que você é humano",
    "verify you are human",
    "prove you are human",
    "security check",
    "checking if the site connection is secure",
    "access denied",
    "acesso negado",
    "unusual traffic",
    "cloudflare",
]

_AUTO_HEAL_INIT_SCRIPT = r"""
(() => {
  const patterns = [
    "accept all", "accept", "allow all", "agree", "aceitar", "aceitar cookies",
    "concordo", "ok", "entendi", "fechar", "close", "dismiss"
  ];
  const norm = (value) => (value || "").toLowerCase().replace(/\s+/g, " ").trim();
  const clickCandidate = () => {
    const elements = Array.from(document.querySelectorAll("button, [role='button'], a, input[type='button'], input[type='submit']"));
    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      if (!rect.width || !rect.height) continue;
      if (style.visibility === "hidden" || style.display === "none") continue;
      const label = norm(el.innerText || el.textContent || el.getAttribute("aria-label") || el.value || "");
      if (!label) continue;
      if (patterns.some((p) => label.includes(p))) {
        try { el.click(); } catch (_) {}
      }
    }
  };
  clickCandidate();
  let runs = 0;
  const timer = setInterval(() => {
    runs += 1;
    clickCandidate();
    if (runs >= 8) clearInterval(timer);
  }, 1200);
})();
"""

_BROWSER_CONTROLLER_PROMPT = (
    "Você é um controlador iterativo de navegador. "
    "Você recebe o estado atual da página e decide APENAS o próximo micro-passo.\n\n"
    "REGRAS:\n"
    "- Responda APENAS JSON válido.\n"
    "- Nunca planeje uma sequência inteira de ações; escolha uma única ação imediata.\n"
    "- Use seletores robustos, preferindo text=\"texto visível\" para botões e links.\n"
    "- Se a página já tiver os dados necessários, finalize.\n"
    "- Se detectar captcha, bloqueio de segurança ou pedido de verificação humana, peça handoff.\n"
    "- Mantenha o campo log curto, honesto e útil para o usuário.\n\n"
    "Formato obrigatório:\n"
    "{"
    "\"status\":\"continue|done|handoff\","
    "\"log\":\"mensagem curta em pt-BR\","
    "\"action\":{\"type\":\"click|write|scroll|wait|press|execute_javascript|screenshot|scrape\","
    "\"selector\":\"...\",\"text\":\"...\",\"key\":\"...\",\"direction\":\"down|up\",\"amount\":500,"
    "\"milliseconds\":1000,\"script\":\"...\"},"
    "\"final_response\":\"texto final bruto e factual quando status=done\","
    "\"handoff_reason\":\"motivo curto quando status=handoff\""
    "}"
)


BrowserProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class PausedBrowserSession:
    resume_token: str
    browser_session_id: str
    connect_url: str
    url: str
    goal: str
    mobile: bool
    include_tags: list[str] | None
    exclude_tags: list[str] | None
    debugger_url: str
    session_viewer_url: str
    created_at: float


class BrowserHandoffRequired(Exception):
    def __init__(
        self,
        *,
        message: str,
        challenge_type: str = "human_verification",
        resume_token: str | None = None,
        session_id: str | None = None,
        debugger_url: str | None = None,
        debugger_fullscreen_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.challenge_type = challenge_type
        self.resume_token = resume_token
        self.session_id = session_id
        self.debugger_url = debugger_url
        self.debugger_fullscreen_url = debugger_fullscreen_url


_PAUSED_BROWSER_SESSIONS: dict[str, PausedBrowserSession] = {}


def _cleanup_paused_sessions() -> None:
    now = time.time()
    expired = [
        token
        for token, session in _PAUSED_BROWSER_SESSIONS.items()
        if (now - session.created_at) >= _BROWSER_RESUME_TTL_SECONDS
    ]
    for token in expired:
        _PAUSED_BROWSER_SESSIONS.pop(token, None)


def get_paused_browser_session(resume_token: str | None) -> dict[str, Any] | None:
    if not resume_token:
        return None
    _cleanup_paused_sessions()
    session = _PAUSED_BROWSER_SESSIONS.get(resume_token)
    if not session:
        return None
    return {
        "resume_token": session.resume_token,
        "browser_session_id": session.browser_session_id,
        "connect_url": session.connect_url,
        "url": session.url,
        "goal": session.goal,
        "mobile": session.mobile,
        "include_tags": session.include_tags,
        "exclude_tags": session.exclude_tags,
        "debugger_url": session.debugger_url,
        "debugger_fullscreen_url": session.session_viewer_url,
        "session_viewer_url": session.session_viewer_url,
        "created_at": session.created_at,
    }


def _build_steel_connect_url(api_key: str, session_id: str, websocket_url: str | None = None) -> str:
    raw = (websocket_url or "").strip()
    if raw:
        separator = "&" if "?" in raw else "?"
        return raw if "apiKey=" in raw else f"{raw}{separator}apiKey={api_key}"
    return f"wss://connect.steel.dev?apiKey={api_key}&sessionId={session_id}"


def _build_steel_live_url(debug_url: str | None) -> str:
    raw = (debug_url or "").strip()
    if not raw:
        return ""
    separator = "&" if "?" in raw else "?"
    suffix = "interactive=true&showControls=true"
    return raw if "interactive=true" in raw else f"{raw}{separator}{suffix}"


def _create_steel_session(steel_client: Any, *, dimensions: dict[str, int]):
    try:
        return steel_client.sessions.create(
            dimensions=dimensions,
            solve_captcha=True,
            timeout=900.0,
        )
    except Exception as exc:
        message = str(exc).lower()
        if "captcha solving is not available" not in message:
            raise
        logger.warning("[BROWSER] Steel sem suporte a solve_captcha no plano atual. Recuando para sessão sem solver.")
        return steel_client.sessions.create(
            dimensions=dimensions,
            timeout=900.0,
        )


def _is_retryable_browser_result(result: str) -> bool:
    text = (result or "").lower()
    return "target page, context or browser has been closed" in text or "page.wait_for_timeout: target page, context or browser has been closed" in text


def _call_openrouter_sync(*, messages: list[dict[str, Any]], model: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    from backend.core.config import get_config

    config = get_config()
    api_key = (config.openrouter_api_key or "").strip()
    if not api_key:
        raise RuntimeError("OpenRouter API key não configurada.")

    payload = {
        "model": model or config.openrouter_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    with httpx.Client(timeout=45.0) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://arcco.ai",
                "X-Title": "Arcco.ai Agent",
            },
            json=payload,
        )
        if response.status_code != 200:
            raise RuntimeError(f"LLM API Error: {response.text}")
        return response.json()


def _emit_progress(
    callback: BrowserProgressCallback | None,
    event_type: str,
    *,
    content: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    if not callback:
        return
    try:
        event: dict[str, Any] = {"type": event_type}
        if content is not None:
            event["content"] = content
        if payload is not None:
            event["payload"] = payload
        callback(event)
    except Exception as exc:
        logger.debug("[BROWSER] Falha ao emitir progresso: %s", exc)


def _normalize_goal(url: str, goal: str | None, actions: list[dict[str, Any]] | None) -> str:
    normalized = (goal or "").strip()
    if normalized:
        return normalized
    if actions:
        hints = []
        for action in actions[:5]:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").strip()
            selector = str(action.get("selector") or "").strip()
            text = str(action.get("text") or "").strip()
            if action_type == "write" and text:
                hints.append(f"preencher '{text[:40]}' em {selector or 'um campo'}")
            elif selector:
                hints.append(f"{action_type} em {selector[:60]}")
            elif action_type:
                hints.append(action_type)
        if hints:
            return (
                f"Use o navegador para concluir a tarefa em {url}. "
                f"Dicas iniciais recebidas: {', '.join(hints)}. "
                "Observe a página a cada passo e extraia o resultado útil."
            )
    return f"Acesse {url}, compreenda a página e extraia o conteúdo ou dado útil para responder ao usuário."


async def execute_browserbase_task(
    url: str,
    goal: str | None = None,
    actions: list[dict[str, Any]] | None = None,
    wait_for: int = 0,
    mobile: bool = False,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    resume_token: str | None = None,
    progress_callback: BrowserProgressCallback | None = None,
) -> str:
    """
    Executa navegação iterativa via Steel.

    - mantém Steel como infraestrutura remota;
    - executa auto-healing silencioso;
    - decide uma ação por iteração;
    - pausa com handoff quando detecta desafio humano.
    """
    from backend.core.config import get_config

    config = get_config()
    api_key = config.steel_api_key

    if not api_key:
        return (
            "Erro: Steel API key não configurada. "
            "Adicione na tabela ApiKeys do Supabase: "
            "provider='steel', api_key='ste_...'."
        )

    try:
        from steel import Steel
    except ImportError as exc:
        return (
            f"Erro de dependência: {exc}. "
            "Execute: pip install steel-sdk playwright && playwright install chromium"
        )

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        return (
            f"Erro de dependência: {exc}. "
            "Execute: pip install playwright && playwright install chromium"
        )

    _cleanup_paused_sessions()
    steel = Steel(steel_api_key=api_key)
    actions = actions or []
    goal = _normalize_goal(url, goal, actions)

    handoff_pending = False
    session_id = ""
    connect_url = ""
    debug_url = ""
    session_viewer_url = ""
    dimensions = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900}

    def _open_fresh_session() -> tuple[str, str, str, str]:
        session = _create_steel_session(steel, dimensions=dimensions)
        fresh_session_id = session.id
        fresh_connect_url = _build_steel_connect_url(api_key, fresh_session_id, getattr(session, "websocket_url", "") or "")
        fresh_debug_url = getattr(session, "debug_url", "") or ""
        fresh_viewer_url = _build_steel_live_url(getattr(session, "session_viewer_url", "") or fresh_debug_url)
        logger.info("[BROWSER] Sessão Steel criada: %s -> %s", fresh_session_id, url)
        return fresh_session_id, fresh_connect_url, fresh_debug_url, fresh_viewer_url

    if resume_token:
        paused = _PAUSED_BROWSER_SESSIONS.get(resume_token)
        if not paused:
            return "Erro: a sessão pausada do navegador não foi encontrada ou expirou."
        session_id = paused.browser_session_id
        connect_url = paused.connect_url
        url = paused.url or url
        goal = paused.goal or goal
        mobile = paused.mobile
        include_tags = paused.include_tags
        exclude_tags = paused.exclude_tags
        debug_url = paused.debugger_url
        session_viewer_url = paused.session_viewer_url
        _emit_progress(progress_callback, "thought", content="Retomando a sessão do navegador...")
    else:
        try:
            session_id, connect_url, debug_url, session_viewer_url = await asyncio.to_thread(
                _open_fresh_session
            )
        except Exception as exc:
            logger.error("[BROWSER] Falha ao criar sessão Steel: %s", exc)
            return f"Erro ao criar sessão na Steel: {exc}"

    try:
        async def _run_once(*, resume_mode: bool) -> str:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    _run_sync_session_loop,
                    connect_url,
                    session_id,
                    url,
                    goal,
                    actions,
                    wait_for,
                    mobile,
                    include_tags,
                    exclude_tags,
                    progress_callback,
                    resume_mode,
                ),
                timeout=_BROWSER_LOOP_TIMEOUT_SECONDS,
            )

        result = await _run_once(resume_mode=bool(resume_token))
        if _is_retryable_browser_result(result):
            _emit_progress(progress_callback, "thought", content="A sessão do navegador fechou inesperadamente. Tentando reconectar...")
            logger.warning("[BROWSER] Sessão %s fechou no meio do fluxo. Tentando reconexão.", session_id)
            result = await _run_once(resume_mode=True)
        if _is_retryable_browser_result(result) and not resume_token:
            _emit_progress(progress_callback, "thought", content="Reconexão insuficiente. Abrindo uma nova sessão do navegador...")
            logger.warning("[BROWSER] Reconexão falhou para a sessão %s. Abrindo nova sessão Steel.", session_id)
            try:
                await asyncio.to_thread(lambda: steel.sessions.release(session_id))
            except Exception:
                pass
            session_id, connect_url, debug_url, session_viewer_url = await asyncio.to_thread(_open_fresh_session)
            result = await _run_once(resume_mode=False)

        if resume_token:
            _PAUSED_BROWSER_SESSIONS.pop(resume_token, None)
        return result
    except BrowserHandoffRequired as exc:
        handoff_pending = True
        try:
            session_info = await asyncio.to_thread(lambda: steel.sessions.retrieve(session_id))
            debug_url = getattr(session_info, "debug_url", "") or debug_url
            session_viewer_url = _build_steel_live_url(
                getattr(session_info, "session_viewer_url", "") or debug_url or session_viewer_url
            )
        except Exception as debug_exc:
            logger.warning("[BROWSER] Falha ao obter URLs da sessão %s: %s", session_id, debug_exc)

        token = resume_token or str(uuid.uuid4())
        _PAUSED_BROWSER_SESSIONS[token] = PausedBrowserSession(
            resume_token=token,
            browser_session_id=session_id,
            connect_url=connect_url,
            url=url,
            goal=goal,
            mobile=mobile,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            debugger_url=debug_url,
            session_viewer_url=session_viewer_url,
            created_at=time.time(),
        )
        raise BrowserHandoffRequired(
            message=exc.message,
            challenge_type=exc.challenge_type,
            resume_token=token,
            session_id=session_id,
            debugger_url=debug_url,
            debugger_fullscreen_url=session_viewer_url,
        ) from exc
    except asyncio.TimeoutError:
        logger.error("[BROWSER] Timeout global de %ss na sessão %s -> %s", _BROWSER_LOOP_TIMEOUT_SECONDS, session_id, url)
        return f"Erro: Timeout de {int(_BROWSER_LOOP_TIMEOUT_SECONDS)}s durante navegação em {url}. O site pode estar lento ou a Steel sobrecarregada."
    finally:
        if session_id and not handoff_pending:
            try:
                await asyncio.to_thread(lambda: steel.sessions.release(session_id))
                logger.info("[BROWSER] Sessão %s liberada.", session_id)
            except Exception as exc:
                logger.warning("[BROWSER] Falha ao liberar sessão %s: %s", session_id, exc)


def _run_sync_session_loop(
    connect_url: str,
    session_id: str,
    url: str,
    goal: str,
    action_hints: list[dict[str, Any]],
    wait_for: int,
    mobile: bool,
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
    progress_callback: BrowserProgressCallback | None,
    resume_mode: bool,
) -> str:
    from playwright.sync_api import sync_playwright

    history: list[str] = []
    last_extracted_text = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(connect_url, timeout=45_000)

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

            try:
                context.add_init_script(_AUTO_HEAL_INIT_SCRIPT)
            except Exception:
                pass

            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(_BROWSER_ACTION_TIMEOUT_MS)
            page.set_default_navigation_timeout(_BROWSER_NAVIGATION_TIMEOUT_MS)

            _emit_progress(progress_callback, "browser_action", payload={
                "status": "navigating",
                "url": url,
                "title": "Retomando sessão..." if resume_mode else f"Acessando {url[:70]}...",
                "actions": [],
            })
            _emit_progress(progress_callback, "thought", content="Acessando o site..." if not resume_mode else "Retomando a navegação pausada...")

            if not resume_mode or page.url in {"about:blank", "chrome-error://chromewebdata/"}:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=_BROWSER_NAVIGATION_TIMEOUT_MS)
                except Exception as exc:
                    logger.warning("[BROWSER] Navegação inicial com falha parcial em %s: %s", url, exc)
                    page.wait_for_timeout(1_500)
                    fallback_text = _extract_page_text_sync(page, include_tags, exclude_tags)
                    if not fallback_text.strip():
                        browser.close()
                        return f"Erro ao carregar a página {url}: {exc}"
            else:
                try:
                    page.bring_to_front()
                except Exception:
                    pass

            if wait_for > 0:
                page.wait_for_timeout(wait_for)

            for step_index in range(1, _BROWSER_MAX_STEPS + 1):
                page.wait_for_timeout(500)

                cleanup_notes = _dismiss_common_ui_noise_sync(page)
                if cleanup_notes:
                    _emit_progress(progress_callback, "thought", content="Detectado pop-up, a tentar fechar...")
                    history.extend(cleanup_notes)

                gate_reason = _detect_human_gate_sync(page)
                if gate_reason:
                    raise BrowserHandoffRequired(message=gate_reason)

                state = _build_page_state_sync(page, include_tags, exclude_tags)
                last_extracted_text = state.get("content_excerpt") or last_extracted_text

                _emit_progress(progress_callback, "browser_action", payload={
                    "status": "reading",
                    "url": state.get("url") or url,
                    "title": state.get("title") or "Lendo página...",
                    "actions": [],
                })

                decision = _decide_next_action_sync(
                    goal=goal,
                    state=state,
                    action_hints=action_hints,
                    history=history,
                    step_index=step_index,
                )
                status = str(decision.get("status") or "continue").strip().lower()
                log_message = str(decision.get("log") or "").strip()
                if log_message:
                    _emit_progress(progress_callback, "thought", content=log_message)

                if status == "handoff":
                    raise BrowserHandoffRequired(
                        message=str(decision.get("handoff_reason") or log_message or "É necessária uma ação humana na página."),
                    )

                if status == "done":
                    final_response = str(decision.get("final_response") or "").strip()
                    extracted_text = _extract_page_text_sync(page, include_tags, exclude_tags)
                    browser.close()
                    return _compose_browser_result(
                        url=state.get("url") or url,
                        title=state.get("title") or "",
                        final_response=final_response,
                        extracted_text=extracted_text or last_extracted_text,
                    )

                action = decision.get("action")
                if not isinstance(action, dict) or not action.get("type"):
                    extracted_text = _extract_page_text_sync(page, include_tags, exclude_tags)
                    browser.close()
                    return _compose_browser_result(
                        url=state.get("url") or url,
                        title=state.get("title") or "",
                        final_response=str(decision.get("final_response") or "").strip(),
                        extracted_text=extracted_text or last_extracted_text,
                    )

                _emit_progress(progress_callback, "browser_action", payload={
                    "status": "acting",
                    "url": state.get("url") or url,
                    "title": state.get("title") or "Interagindo com a página...",
                    "actions": [str(action.get("type"))],
                })

                action_note = _apply_action_sync(page, action, include_tags, exclude_tags)
                history.append(action_note)

                gate_reason = _detect_human_gate_sync(page)
                if gate_reason:
                    raise BrowserHandoffRequired(message=gate_reason)

            extracted_text = _extract_page_text_sync(page, include_tags, exclude_tags)
            browser.close()
            return _compose_browser_result(
                url=page.url or url,
                title=page.title(),
                final_response="",
                extracted_text=extracted_text or last_extracted_text,
            )

    except BrowserHandoffRequired:
        raise
    except Exception as exc:
        logger.error("[BROWSER] Erro crítico na sessão %s: %s", session_id, exc)
        return f"Erro durante navegação com Steel: {exc}"


def _compose_browser_result(url: str, title: str, final_response: str, extracted_text: str) -> str:
    final_response = (final_response or "").strip()
    extracted_text = (extracted_text or "").strip()

    if len(extracted_text) > _MAX_CONTENT_CHARS:
        extracted_text = extracted_text[:_MAX_CONTENT_CHARS] + "\n\n... [Truncado por limite de tokens]"

    if final_response and extracted_text and final_response not in extracted_text:
        return f"Resultado observado em {url} ({title or 'sem título'}):\n\n{final_response}\n\nConteúdo visível relevante:\n\n{extracted_text}"
    if final_response:
        return final_response
    if extracted_text:
        return f"Conteúdo extraído de {url} ({title or 'sem título'}):\n\n{extracted_text}"
    return f"Página acessada em {url} ({title or 'sem título'}), mas nenhum conteúdo relevante foi encontrado."


def _build_page_state_sync(
    page: Any,
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> dict[str, Any]:
    content_excerpt = _extract_page_text_sync(page, include_tags, exclude_tags)
    interactive_elements = _extract_interactive_elements_sync(page)
    return {
        "title": page.title(),
        "url": page.url,
        "content_excerpt": content_excerpt[:_BROWSER_VISIBLE_TEXT_CHARS],
        "interactive_elements": interactive_elements[:_BROWSER_MAX_INTERACTIVE_ITEMS],
    }


def _extract_interactive_elements_sync(page: Any) -> list[dict[str, str]]:
    try:
        return page.evaluate(
            """
            () => {
              const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();
              const selectorFor = (el, text, tag, id, name, placeholder) => {
                if (text) return `text="${text.replace(/"/g, '\\"').slice(0, 80)}"`;
                if (id) return `#${id}`;
                if (name && ["input", "textarea", "select"].includes(tag)) return `${tag}[name="${name}"]`;
                if (placeholder) return `${tag}[placeholder="${placeholder.replace(/"/g, '\\"').slice(0, 80)}"]`;
                return tag;
              };
              const nodes = Array.from(document.querySelectorAll("button, a, input, textarea, select, [role='button'], [role='link'], [role='textbox']"));
              const visible = nodes.filter((el) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
              });
              return visible.slice(0, 40).map((el) => {
                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute("role") || tag;
                const text = clean(el.innerText || el.textContent || el.value || "");
                const aria = clean(el.getAttribute("aria-label") || "");
                const placeholder = clean(el.getAttribute("placeholder") || "");
                const name = clean(el.getAttribute("name") || "");
                const id = clean(el.id || "");
                return {
                  role,
                  text: text.slice(0, 100),
                  aria_label: aria.slice(0, 100),
                  placeholder: placeholder.slice(0, 100),
                  selector_hint: selectorFor(el, text || aria, tag, id, name, placeholder),
                };
              });
            }
            """
        )
    except Exception as exc:
        logger.debug("[BROWSER] Falha ao extrair elementos interativos: %s", exc)
        return []


def _dismiss_common_ui_noise_sync(page: Any) -> list[str]:
    notes: list[str] = []

    try:
        page.evaluate(_AUTO_HEAL_INIT_SCRIPT)
    except Exception:
        pass

    for keyword in _COOKIE_KEYWORDS + _CLOSE_KEYWORDS:
        try:
            locator = page.locator(f'text="{keyword}"').first
            if locator.count() > 0:
                locator.click(timeout=1_500)
                notes.append(f"click(auto-dismiss:{keyword})")
                page.wait_for_timeout(300)
        except Exception:
            continue

    try:
        removed = page.evaluate(
            """
            () => {
              const targets = [];
              const terms = ["cookie", "cookies", "newsletter", "subscribe", "cadastre-se", "inscreva-se", "desconto", "discount"];
              const clean = (value) => (value || "").toLowerCase().replace(/\\s+/g, " ").trim();
              for (const el of Array.from(document.querySelectorAll("div, section, aside, dialog"))) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 220 || rect.height < 120) continue;
                const style = window.getComputedStyle(el);
                if (!["fixed", "sticky"].includes(style.position)) continue;
                const text = clean(el.innerText || el.textContent || "");
                if (terms.some((term) => text.includes(term))) targets.push(el);
              }
              let removed = 0;
              for (const el of targets) {
                el.remove();
                removed += 1;
              }
              return removed;
            }
            """
        )
        if removed:
            notes.append(f"remove(overlays:{removed})")
    except Exception:
        pass

    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    return notes


def _detect_human_gate_sync(page: Any) -> str | None:
    try:
        body_text = page.locator("body").inner_text(timeout=3_000).lower()
    except Exception:
        body_text = ""

    for pattern in _HUMAN_GATE_PATTERNS:
        if pattern in body_text:
            return f"Verificação humana detectada na página ({pattern})."

    try:
        frame_urls = " ".join(frame.url.lower() for frame in page.frames)
        for pattern in ("recaptcha", "hcaptcha", "captcha", "challenge-platform"):
            if pattern in frame_urls:
                return f"Verificação humana detectada na página ({pattern})."
    except Exception:
        pass

    return None


def _decide_next_action_sync(
    *,
    goal: str,
    state: dict[str, Any],
    action_hints: list[dict[str, Any]],
    history: list[str],
    step_index: int,
) -> dict[str, Any]:
    from backend.agents import registry
    from backend.core.config import get_config

    model = registry.get_model("planner") or registry.get_model("chat") or get_config().openrouter_model
    user_prompt = (
        f"Objetivo do usuário:\n{goal}\n\n"
        f"Iteração atual: {step_index}/{_BROWSER_MAX_STEPS}\n\n"
        "Dicas opcionais recebidas do chamador (NÃO execute cegamente em bloco; use apenas como pistas):\n"
        f"{json.dumps(action_hints or [], ensure_ascii=False)}\n\n"
        "Histórico recente de ações:\n"
        f"{json.dumps(history[-6:], ensure_ascii=False)}\n\n"
        "Estado atual da página:\n"
        f"{json.dumps(state, ensure_ascii=False)}\n\n"
        "Decida o próximo micro-passo."
    )

    try:
        response = _call_openrouter_sync(
            messages=[
                {"role": "system", "content": _BROWSER_CONTROLLER_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            max_tokens=600,
            temperature=0.1,
        )
        raw_content = (
            response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        parsed = _parse_controller_response(raw_content)
        if parsed:
            return parsed
    except Exception as exc:
        logger.warning("[BROWSER] Falha no controlador iterativo: %s", exc)

    content_excerpt = str(state.get("content_excerpt") or "").strip()
    if content_excerpt:
        return {
            "status": "done",
            "log": "Dados visíveis localizados. Consolidando a resposta...",
            "final_response": content_excerpt,
        }

    return {
        "status": "continue",
        "log": "Aguardando carregamento adicional da página...",
        "action": {"type": "wait", "milliseconds": 1200},
    }


def _parse_controller_response(raw_content: str) -> dict[str, Any] | None:
    content = (raw_content or "").strip()
    if not content:
        return None

    candidates = [content]
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(content[first_brace:last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        status = str(parsed.get("status") or "").strip().lower()
        if status not in {"continue", "done", "handoff"}:
            continue
        return parsed
    return None


def _apply_action_sync(
    page: Any,
    action: dict[str, Any],
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> str:
    action_type = str(action.get("type") or "").strip()
    try:
        if action_type == "click":
            selector = str(action.get("selector") or "").strip()
            if not selector:
                raise ValueError("selector ausente")
            page.locator(selector).first.click(timeout=_BROWSER_ACTION_TIMEOUT_MS)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=_BROWSER_ACTION_TIMEOUT_MS)
            except Exception:
                pass
            page.wait_for_timeout(700)
            return f"click({selector})"

        if action_type == "write":
            selector = str(action.get("selector") or "").strip()
            text = str(action.get("text") or "")
            if not selector:
                raise ValueError("selector ausente")
            page.locator(selector).first.fill(text, timeout=_BROWSER_ACTION_TIMEOUT_MS)
            page.wait_for_timeout(400)
            return f"write({selector}, {text[:40]})"

        if action_type == "scroll":
            direction = str(action.get("direction") or "down").strip().lower()
            amount = int(action.get("amount") or 700)
            delta = amount if direction != "up" else -amount
            page.evaluate(f"window.scrollBy(0, {delta})")
            page.wait_for_timeout(500)
            return f"scroll({direction}, {amount})"

        if action_type == "wait":
            ms = max(0, int(action.get("milliseconds") or 1000))
            page.wait_for_timeout(ms)
            return f"wait({ms}ms)"

        if action_type == "press":
            key = str(action.get("key") or "Enter")
            selector = str(action.get("selector") or "").strip()
            if selector:
                page.locator(selector).first.press(key, timeout=_BROWSER_ACTION_TIMEOUT_MS)
            else:
                page.keyboard.press(key)
            page.wait_for_timeout(400)
            return f"press({key})"

        if action_type == "execute_javascript":
            script = str(action.get("script") or "")
            result = page.evaluate(script)
            return f"js({str(result)[:80]})"

        if action_type == "screenshot":
            screenshot_note = _try_screenshot_sync(page)
            return f"screenshot({screenshot_note})"

        if action_type == "scrape":
            excerpt = _extract_page_text_sync(page, include_tags, exclude_tags)
            return f"scrape({len(excerpt)} chars)"

        return f"desconhecida({action_type})"
    except Exception as exc:
        logger.warning("[BROWSER] Falha na micro-ação '%s': %s", action_type, exc)
        return f"erro({action_type}: {str(exc)[:80]})"


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
        logger.error("[BROWSER] Falha na extração de texto: %s", exc)
        return ""


def _try_screenshot_sync(page: Any) -> str:
    try:
        screenshot_bytes: bytes = page.screenshot(full_page=False)
        try:
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
            return "ok (sem upload)"
    except Exception as exc:
        return f"falhou: {str(exc)[:40]}"
