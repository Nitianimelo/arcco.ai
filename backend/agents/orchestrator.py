"""
Orquestrador Multi-Agente do Arcco (Arquitetura Supervisor-Worker / ReAct).

Fluxo de execução:
  1. O Agente Supervisor (único a conversar com o usuário) recebe a requisição.
  2. O Supervisor decide se responde diretamente ou se usa Ferramentas (Sub-Agentes).
  3. Ao usar uma Ferramenta Não-Terminal (Busca, Arquivos):
      - O sub-agente executa a tarefa.
      - Guardrails internos validam consistência e links obrigatórios.
      - O resultado volta para o Supervisor redigir a resposta final amigável.
  4. Ao usar uma Ferramenta Terminal (Design, Text Generator):
      - O sub-agente executa a tarefa.
      - O resultado bruto (HTML/texto) é enviado diretamente ao usuário via SSE.
      - O loop do Supervisor é encerrado imediatamente (proteção do Front-end).
  5. Ferramentas diretas (web_search, execute_python):
      - Executadas diretamente pelo executor, resultado volta ao Supervisor.
"""

import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator

from backend.core.llm import call_openrouter, stream_openrouter
from backend.agents import registry
from backend.agents.capabilities import get_capability_by_route, get_direct_dispatch_routes, get_runtime_semantics, route_requires_link_only
from backend.agents.contracts import CapabilityResult, PolicyDecisionContract, RouteReplanDecisionContract, ValidationIssueContract, ValidationResultContract
from backend.agents.clarifier import build_follow_up_questions
from backend.agents.handoffs import build_browser_handoff_state, build_mass_document_handoff, build_search_to_spreadsheet_handoff
from backend.agents.planner import ClarificationQuestion
from backend.agents.dispatcher import dispatch_direct_route, planner_action_to_tool_name, resolve_runtime_target
from backend.agents.open_solver import build_open_solver_prompt, init_open_solver_context, update_open_solver_context
from backend.agents.preconditions import evaluate_preconditions
from backend.agents.task_types import get_task_type_definition, infer_task_type, resolve_execution_engine
from backend.agents.validators import validate_capability_execution
from backend.agents.workflow_policy import decide_on_route_failure, decide_on_validation
from backend.agents.step_replanner import build_replanned_args, decide_route_replan
from backend.agents.workflow_state import (
    build_browser_workflow_stages,
    build_mass_document_stages,
    build_open_solver_stages,
    mass_document_updates_for_step_result,
    mass_document_updates_for_step_start,
    update_workflow_stages,
)
from backend.agents.executor import execute_tool
from backend.agents.tools import SUPERVISOR_TOOLS, SPY_PAGES_TOOLS
from backend.services.browser_service import BrowserHandoffRequired, get_paused_browser_session
from backend.skills import loader as skills_loader

logger = logging.getLogger(__name__)

# ── Timeout para ferramentas pesadas (browser, deep_research) ────────────────
_BROWSER_TIMEOUT = 60.0   # segundos
_SEARCH_TIMEOUT = 30.0    # segundos
_HEARTBEAT_INTERVAL = 5.0 # segundos
_SUPERVISOR_TIMEOUT = 60.0
_SKILL_TIMEOUT = 60.0
_SPECIALIST_TIMEOUT = 90.0
_TERMINAL_TIMEOUT = 90.0
_MAX_CONTEXT_ENTRY_CHARS = 4000
_MAX_ACCUMULATED_CONTEXT_CHARS = 24000


async def _exec_with_heartbeat(coro, heartbeat_fn, timeout: float, interval: float = _HEARTBEAT_INTERVAL):
    """
    Executa coroutine com heartbeat SSE em tempo real e timeout global.
    É um async generator: yield heartbeat strings enquanto a tool roda.
    O resultado final é yielded como dict {"_result": value}.
    Uso:
        async for event in _exec_with_heartbeat(...):
            if isinstance(event, dict) and "_result" in event:
                result = event["_result"]
            else:
                yield event  # heartbeat SSE
    """
    task = asyncio.create_task(coro)
    elapsed = 0.0

    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=interval)
            break
        except asyncio.TimeoutError:
            elapsed += interval
            if elapsed >= timeout:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                yield {"_result": None, "_timeout": True, "_elapsed": elapsed}
                return
            yield heartbeat_fn(elapsed)

    try:
        yield {"_result": task.result()}
    except Exception as exc:
        yield {"_result": None, "_error": str(exc)}


async def _call_openrouter_with_timeout(*, timeout: float, label: str, **kwargs) -> dict:
    try:
        return await asyncio.wait_for(call_openrouter(**kwargs), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(f"{label} excedeu {int(timeout)}s.") from exc


# ── Pre-action Acknowledgement (fallback quando o modelo não gera content) ───

def _build_pre_action_ack(tool_calls: list) -> str | None:
    """Gera mensagem contextual a partir da primeira tool_call quando o LLM não produz content."""
    if not tool_calls:
        return None
    tc = tool_calls[0]
    name = tc.get("function", {}).get("name", "")
    try:
        args = json.loads(tc["function"].get("arguments", "{}"))
    except (json.JSONDecodeError, KeyError):
        args = {}
    if name == "ask_web_search":
        q = args.get("query", "")
        return f"Vou pesquisar sobre {q[:80]}..." if q else "Pesquisando na web..."
    if name == "ask_browser":
        url = args.get("url", "")
        return f"Acessando {url[:60]}..." if url else "Acessando o site..."
    if name == "execute_python":
        return "Processando com código..."
    if name == "ask_design_generator":
        return "Criando o design..."
    if name == "ask_text_generator":
        return "Redigindo o documento..."
    if name == "deep_research":
        q = args.get("query", "")
        return f"Iniciando pesquisa aprofundada sobre {q[:60]}..." if q else "Iniciando pesquisa aprofundada..."
    if name == "ask_file_modifier":
        return "Modificando o arquivo..."
    if name == "read_session_file":
        fn = args.get("file_name", "")
        return f"Consultando o arquivo {fn[:40]}..." if fn else "Consultando o arquivo anexado..."
    if name == "analyze_web_pages":
        urls = args.get("urls", [])
        if urls:
            return f"Analisando {len(urls)} site(s) via SimilarWeb..."
        return "Analisando sites via SimilarWeb..."
    return None


DIRECT_DISPATCH_ROUTES = get_direct_dispatch_routes()
_MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)', re.IGNORECASE)
_ATTACHMENT_READ_PATTERN = re.compile(
    r"\b(leia|ler|resuma|resumir|analise|analisar|extraia|extrair|consulte|consulta|"
    r"qual|quais|me diga|conte[uú]do|anexo|arquivo|pdf|planilha|documento)\b",
    re.IGNORECASE,
)
_ATTACHMENT_MODIFY_PATTERN = re.compile(
    r"\b(altere|alterar|modifique|modificar|edite|editar|atualize|atualizar|"
    r"substitua|substituir|mude|mudar|adicione|adicionar|remova|remover|preencha|preencher)\b",
    re.IGNORECASE,
)
_VISUAL_REQUEST_PATTERN = re.compile(
    r"\b(banner|post|carrossel|slide|apresenta[cç][aã]o|flyer|panfleto|landing page|layout|pe[cç]a visual)\b",
    re.IGNORECASE,
)
_TOOL_CALL_LEAK_PATTERN = re.compile(
    r'^\s*(?:```(?:json)?\s*)?\{[\s\S]*"(?:tool|function|parameters)"\s*:',
    re.IGNORECASE,
)
_RAW_URL_CONTEXT_PATTERN = re.compile(r"https?://[^\s\)\]]+", re.IGNORECASE)
_SEARCH_SUMMARY_CONTEXT_PATTERN = re.compile(r"\*\*Resumo:\*\*(.+?)(?:\n\n|\Z)", re.IGNORECASE | re.DOTALL)

# ── Utilitários SSE ──────────────────────────────────────────────────────────

def sse(event_type: str, content: str) -> str:
    return f'data: {{"type": "{event_type}", "content": {json.dumps(content)}}}\n\n'


def _browser_handoff_payload(exc: BrowserHandoffRequired, url: str) -> dict:
    live_url = exc.debugger_fullscreen_url or exc.debugger_url or ""
    return {
        "kind": "browser_handoff",
        "message": exc.message,
        "resume_token": exc.resume_token,
        "action_url": live_url,
        "action_label": "Abrir Sessão ao Vivo",
        "questions": [
            {
                "type": "choice",
                "text": (
                    "Há um obstáculo visual no site. Abra a sessão ao vivo, resolva o desafio "
                    "e depois clique em continuar para a automação retomar do ponto em que parou."
                ),
                "options": ["Já resolvi, pode continuar"],
            }
        ],
        "browser_action": {
            "status": "awaiting_user",
            "url": url,
            "title": exc.message[:120] if exc.message else "Aguardando ação humana",
            "live_url": live_url,
        },
    }


async def _exec_browser_with_progress(
    func_args: dict,
    *,
    user_id: str | None,
    timeout: float,
) -> AsyncGenerator[Any, None]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _on_browser_event(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    task = asyncio.create_task(
        execute_tool("ask_browser", func_args, user_id=user_id, event_callback=_on_browser_event)
    )
    started_at = loop.time()
    next_heartbeat_at = started_at + _HEARTBEAT_INTERVAL

    while True:
        if task.done() and queue.empty():
            break

        now = loop.time()
        elapsed = now - started_at
        if elapsed >= timeout:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            yield {"_result": None, "_timeout": True, "_elapsed": elapsed}
            return

        wait_timeout = max(0.1, min(1.0, next_heartbeat_at - now))
        try:
            event = await asyncio.wait_for(queue.get(), timeout=wait_timeout)
            event_type = str(event.get("type") or "")
            if event_type == "thought":
                content = str(event.get("content") or "").strip()
                if content:
                    yield sse("thought", content)
            elif event_type == "browser_action":
                payload = event.get("payload") or {}
                yield sse("browser_action", json.dumps(payload))
        except asyncio.TimeoutError:
            now = loop.time()
            if now >= next_heartbeat_at:
                elapsed = now - started_at
                yield sse("steps", f"<step>Navegador ativo — {int(elapsed)}s...</step>")
                next_heartbeat_at = now + _HEARTBEAT_INTERVAL

    try:
        yield {"_result": await task}
    except BrowserHandoffRequired as exc:
        yield {"_handoff": exc}
    except Exception as exc:
        yield {"_result": None, "_error": str(exc)}


def _extract_markdown_links(content: str) -> list[tuple[str, str]]:
    return _MARKDOWN_LINK_PATTERN.findall(content or "")


def _extract_storage_markdown_links(content: str) -> list[tuple[str, str]]:
    links = _extract_markdown_links(content)
    return [
        (label, url)
        for label, url in links
        if "/storage/v1/object/" in url or "/storage/v1/object/public/" in url
    ]


def _extract_source_urls_from_text(content: str) -> list[str]:
    urls = [url.rstrip(").,") for _, url in _extract_markdown_links(content or "")]
    urls.extend(url.rstrip(").,") for url in _RAW_URL_CONTEXT_PATTERN.findall(content or ""))
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _is_error_result(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    error_markers = (
        lowered.startswith("erro"),
        lowered.startswith("error"),
        "client error" in lowered,
        "server error" in lowered,
        "payment required" in lowered,
        "unauthorized" in lowered,
        "excedeu 90s" in lowered,
        "timeout" in lowered and ("erro" in lowered or "falh" in lowered),
        "tool call obrigatório não emitido" in lowered,
        "falhou:" in lowered,
        "não encontrado na sessão" in lowered,
        "nao encontrado na sessao" in lowered,
        "nenhum arquivo disponível" in lowered,
        "nenhum arquivo disponivel" in lowered,
        "nenhum arquivo anexado" in lowered,
    )
    return any(error_markers)


def _sanitize_user_facing_response(content: str, *, had_failures: bool = False) -> str:
    text = (content or "").strip()
    if not text:
        return "Desculpe, não consegui gerar uma resposta confiável."
    if _TOOL_CALL_LEAK_PATTERN.search(text) or ('"tool"' in text and "ask_" in text):
        if had_failures:
            return (
                "Não consegui concluir a tarefa com confiabilidade porque uma ou mais ferramentas "
                "falharam durante a execução. Ajuste a configuração necessária e tente novamente."
            )
        return "Desculpe, a resposta final saiu em formato interno inválido. Tente novamente."
    return text


def _get_session_inventory_items(session_id: str | None) -> list[dict[str, Any]]:
    if not session_id:
        return []
    try:
        from backend.services.session_extraction_service import recover_pending_session_files
        from backend.services.session_file_service import list_session_files, touch_session

        touch_session(session_id)
        recover_pending_session_files(session_id)
        return list_session_files(session_id)
    except Exception as exc:
        logger.error("Falha ao ler inventário da sessão %s: %s", session_id, exc)
        return []


def _select_referenced_session_file(user_intent: str, session_id: str | None) -> dict[str, Any] | None:
    inventory = _get_session_inventory_items(session_id)
    if not inventory:
        return None

    normalized_intent = (user_intent or "").lower()
    for item in inventory:
        file_name = str(item.get("original_name") or item.get("file_name") or "").strip()
        if file_name and file_name.lower() in normalized_intent:
            return item

    if len(inventory) == 1 and _ATTACHMENT_READ_PATTERN.search(user_intent or ""):
        return inventory[0]

    return None


def _intent_requires_session_files(user_intent: str) -> bool:
    normalized = (user_intent or "").lower()
    file_markers = (
        "pdf",
        "arquivo",
        "arquivos",
        "anexo",
        "anexos",
        "documento",
        "documentos",
    )
    file_ops = (
        "extrair",
        "reorganizar",
        "converter",
        "transformar",
        "gerar outro",
        "novo pdf",
        "crie outro design",
        "mantendo as mesmas informacoes",
        "mantendo as mesmas informações",
    )
    return any(token in normalized for token in file_markers) and any(token in normalized for token in file_ops)


def _build_missing_session_files_validation(summary: str) -> ValidationResultContract:
    return ValidationResultContract(
        validator_id="open_solver_intake",
        task_type="open_problem_solving",
        capability_id="session_file_read",
        status="clarification_recommended",
        summary=summary,
        issues=[
            ValidationIssueContract(
                code="missing_required_session_files",
                severity="high",
                message="O pedido depende explicitamente de anexos, mas não há arquivos válidos disponíveis no inventário da sessão.",
                field_name="session_files",
            )
        ],
        clarification_needed=True,
    )


def _resolve_session_file_request(
    *,
    session_id: str | None,
    requested_file_name: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    inventory = _get_session_inventory_items(session_id)
    if not inventory:
        return None, "Nenhum arquivo anexado está disponível nesta sessão."

    inventory_by_name: dict[str, dict[str, Any]] = {}
    for item in inventory:
        file_name = str(item.get("original_name") or item.get("file_name") or "").strip()
        if file_name:
            inventory_by_name[file_name] = item

    normalized_request = str(requested_file_name or "").strip()
    lowered_request = normalized_request.lower()
    placeholder_markers = (
        "[nome_do_arquivo",
        "[nenhum arquivo",
        "forneça o arquivo",
        "forneca o arquivo",
    )
    if any(marker in lowered_request for marker in placeholder_markers):
        normalized_request = ""
    if normalized_request and normalized_request in inventory_by_name:
        return inventory_by_name[normalized_request], None

    if len(inventory) == 1 and not normalized_request:
        return inventory[0], None

    available_names = [name for name in inventory_by_name.keys() if name]
    if normalized_request:
        return None, (
            f"O arquivo '{normalized_request}' não existe no inventário atual da sessão. "
            f"Arquivos disponíveis: {', '.join(available_names) if available_names else 'nenhum'}."
        )

    return None, "Há mais de um anexo disponível e nenhum arquivo exato foi selecionado para leitura."


def _normalize_plan_for_session_files(plan_output, *, user_intent: str, session_id: str | None):
    ref = _select_referenced_session_file(user_intent, session_id)
    if not ref:
        return plan_output

    if getattr(plan_output, "needs_clarification", False):
        return plan_output

    if _ATTACHMENT_MODIFY_PATTERN.search(user_intent or ""):
        return plan_output

    file_name = str(ref.get("original_name") or ref.get("file_name") or "").strip()
    if not file_name:
        return plan_output

    from backend.agents.planner import PlanStep

    plan_output.is_complex = True
    plan_output.steps = [
        PlanStep(
            step=1,
            action="session_file",
            detail=f"Ler o anexo da sessão '{file_name}' e extrair apenas os dados necessários para responder ao pedido.",
            is_terminal=False,
        ),
        PlanStep(
            step=2,
            action="direct_answer",
            detail="Responder ao usuário usando exclusivamente o conteúdo validado do anexo lido.",
            is_terminal=True,
        ),
    ]
    logger.info("[ORCHESTRATOR] Plano normalizado para leitura de anexo da sessão: %s", file_name)
    return plan_output


def _normalize_plan_for_visual_requests(plan_output, *, user_intent: str):
    normalized = (user_intent or "").lower()
    mentions_instagram = "instagram" in normalized or "insta" in normalized
    asks_post_like = any(token in normalized for token in ("post", "arte", "criativo", "imagem", "peça", "peca"))
    has_specific_visual_format = any(
        token in normalized
        for token in ("story", "stories", "feed", "carrossel", "carousel", "slide", "slides", "apresenta", "deck", "banner", "thumb", "thumbnail", "a4")
    )
    if mentions_instagram and asks_post_like and not has_specific_visual_format:
        plan_output.needs_clarification = True
        plan_output.questions = [
            ClarificationQuestion(
                type="choice",
                text="Qual formato você quer para essa peça de Instagram?",
                options=["Story", "Feed", "Carrossel"],
            )
        ]
        plan_output.acknowledgment = "Preciso só do formato antes de gerar a peça."
        plan_output.steps = []
        logger.info("[ORCHESTRATOR] Pedido visual genérico do Instagram convertido em clarificação obrigatória.")
        return plan_output

    if plan_output.steps and not plan_output.is_complex:
        has_non_direct_step = any(step.action != "direct_answer" for step in plan_output.steps)
        if has_non_direct_step:
            plan_output.is_complex = True
            logger.info("[ORCHESTRATOR] Plano com steps não-diretos forçado para fluxo complexo.")

    design_indexes = [idx for idx, step in enumerate(plan_output.steps) if step.action == "design_generator"]
    if not design_indexes:
        return plan_output

    first_design_idx = design_indexes[0]
    truncated = plan_output.steps[: first_design_idx + 1]
    for idx, step in enumerate(truncated, start=1):
        step.step = idx
        step.is_terminal = idx == len(truncated)
    plan_output.steps = truncated
    logger.info("[ORCHESTRATOR] Plano visual truncado para encerrar em design_generator.")
    return plan_output


def _normalize_plan_for_mass_document_requests(plan_output, *, user_intent: str, session_id: str | None):
    if getattr(plan_output, "needs_clarification", False):
        return plan_output

    inventory = _get_session_inventory_items(session_id)
    if not inventory:
        return plan_output

    normalized = (user_intent or "").lower()
    mass_doc_signals = (
        "ocr",
        "rag",
        "documentos",
        "documentos em lote",
        "vários pdf",
        "varios pdf",
        "lote",
        "contratos",
        "processos",
    )
    objective_signals = (
        "resumo",
        "relatório",
        "relatorio",
        "compar",
        "risco",
        "planilha",
        "tabela",
        "slides",
        "apresentação",
        "apresentacao",
        "perguntas",
    )

    has_many_docs = len(inventory) >= 2
    likely_mass_doc = has_many_docs and any(signal in normalized for signal in mass_doc_signals)
    if not likely_mass_doc:
        return plan_output

    has_clear_objective = any(signal in normalized for signal in objective_signals)
    if has_clear_objective:
        return plan_output

    plan_output.task_type = "mass_document_analysis"
    plan_output.is_complex = True
    plan_output.needs_clarification = True
    plan_output.acknowledgment = "Preciso só do objetivo principal antes de processar o lote de documentos."
    plan_output.questions = [
        ClarificationQuestion(
            type="choice",
            text="O que você quer extrair primeiro desse conjunto de documentos?",
            options=["Resumo executivo", "Tabela comparativa", "Riscos e inconsistências"],
            helper_text="Isso reduz custo e melhora a precisão do OCR/RAG.",
        ),
        ClarificationQuestion(
            type="choice",
            text="Como você quer receber a primeira saída?",
            options=["Resumo executivo", "Tabela comparativa", "Relatório detalhado"],
            helper_text="Escolher o formato evita processar conteúdo desnecessário logo de início.",
        ),
    ]
    plan_output.steps = []
    logger.info("[ORCHESTRATOR] Lote de documentos convertido em clarificação antes de OCR/RAG.")
    return plan_output


def _normalize_plan_for_open_problem_solving(plan_output, *, user_intent: str, session_id: str | None):
    normalized = (user_intent or "").lower()
    inventory = _get_session_inventory_items(session_id)

    transform_signals = (
        "extrair",
        "converter",
        "transformar",
        "reorganizar",
        "recombinar",
        "gerar outro",
        "novo pdf",
        "html",
        "python",
        "script",
        "misturar",
    )
    file_signals = ("pdf", "docx", "xlsx", "planilha", "documento", "arquivo", "anexo", "imagem")
    output_signals = ("pdf", "html", "docx", "planilha", "excel", "png", "imagem", "apresentação", "apresentacao")
    asks_visual_output = any(token in normalized for token in ("html", "layout", "design", "visual", "apresentação", "apresentacao", "slide"))

    has_transform_intent = sum(1 for token in transform_signals if token in normalized) >= 2
    has_file_context = bool(inventory) or any(token in normalized for token in file_signals)
    if not (has_transform_intent and has_file_context):
        return plan_output

    plan_output.task_type = "open_problem_solving"
    plan_output.is_complex = True

    if _intent_requires_session_files(user_intent) and not inventory:
        validation_result = _build_missing_session_files_validation(
            "Preciso dos arquivos citados antes de iniciar a resolução aberta."
        )
        plan_output.needs_clarification = True
        plan_output.acknowledgment = "Preciso dos anexos corretos antes de extrair texto, imagens ou reconstruir o material."
        plan_output.questions = build_follow_up_questions(
            task_type="open_problem_solving",
            validation_result=validation_result,
        )
        plan_output.steps = []
        logger.info("[ORCHESTRATOR] Open problem solving bloqueado por ausência de anexos obrigatórios.")
        return plan_output

    has_clear_output = any(token in normalized for token in output_signals)
    if not has_clear_output and not getattr(plan_output, "needs_clarification", False):
        plan_output.needs_clarification = True
        plan_output.acknowledgment = "Preciso alinhar o entregável final antes de montar a solução."
        plan_output.questions = build_follow_up_questions(
            task_type="open_problem_solving",
            validation_result=ValidationResultContract(
                validator_id="open_problem_solver_intake",
                task_type="open_problem_solving",
                capability_id="planner",
                status="clarification_recommended",
                summary="Pedido singular identificado, mas o entregável final ainda não está explícito.",
                issues=[
                    ValidationIssueContract(
                        code="open_solver_missing_output_target",
                        severity="warning",
                        message="O objetivo sugere composição livre de capabilities, mas o formato final ainda não está nítido.",
                    )
                ],
                clarification_needed=True,
            ),
        )
        plan_output.steps = []
        logger.info("[ORCHESTRATOR] Pedido singular convertido em clarificação para open_problem_solving.")
        return plan_output

    from backend.agents.planner import PlanStep

    steps = []
    if inventory:
        available_files = [
            str(item.get("original_name") or item.get("file_name") or "").strip()
            for item in inventory
            if str(item.get("original_name") or item.get("file_name") or "").strip()
        ]
        file_label = ", ".join(available_files[:3])
        if len(available_files) > 3:
            file_label += f" e mais {len(available_files) - 3}"
        steps.append(
            PlanStep(
                step=1,
                action="session_file",
                detail=(
                    f"Ler os anexos necessários da sessão ({file_label or 'arquivos anexados'}) "
                    "e extrair somente os insumos necessários para resolver o objetivo final."
                ),
                is_terminal=False,
            )
        )

    steps.append(
        PlanStep(
            step=len(steps) + 1,
            action="python",
            detail=(
                "Resolver o problema de forma aberta usando código Python e artefatos intermediários quando necessário. "
                "É permitido extrair texto, imagens, estruturar dados, gerar novos arquivos e preparar insumos para o passo final."
            ),
            is_terminal=not asks_visual_output,
        )
    )

    if asks_visual_output:
        steps.append(
            PlanStep(
                step=len(steps) + 1,
                action="design_generator",
                detail="Transformar a estrutura intermediária em um artefato visual editável e pronto para preview ou exportação.",
                is_terminal=True,
            )
        )

    plan_output.steps = steps
    if not plan_output.acknowledgment:
        plan_output.acknowledgment = "Vou montar a solução por etapas e escolher as capacidades necessárias para resolver isso com flexibilidade."
    logger.info("[ORCHESTRATOR] Plano convertido para open_problem_solving.")
    return plan_output


def _question_is_file_selection_prompt(question: Any) -> bool:
    text = str(getattr(question, "text", "") or "").lower()
    return any(marker in text for marker in ("qual arquivo", "qual fonte", "forneça o arquivo", "forneca o arquivo", "forneça o link", "forneca o link"))


def _reconcile_plan_clarification_with_inventory(plan_output, *, session_id: str | None):
    inventory = _get_session_inventory_items(session_id)
    ready_files = [
        item for item in inventory
        if str(item.get("status") or "").strip() == "ready"
    ]
    if len(ready_files) != 1 or not getattr(plan_output, "needs_clarification", False):
        return plan_output

    questions = list(getattr(plan_output, "questions", []) or [])
    filtered_questions = [question for question in questions if not _question_is_file_selection_prompt(question)]
    if len(filtered_questions) == len(questions):
        return plan_output

    plan_output.questions = filtered_questions
    selected_name = str(ready_files[0].get("original_name") or ready_files[0].get("file_name") or "arquivo anexado").strip()
    if filtered_questions:
        plan_output.acknowledgment = (
            f"Vou usar o anexo '{selected_name}' e preciso alinhar só os detalhes finais antes de executar."
        )
    else:
        plan_output.needs_clarification = False
        plan_output.acknowledgment = f"Vou usar o anexo '{selected_name}' como fonte principal."
    logger.info("[ORCHESTRATOR] Clarificação reconciliada com inventário real da sessão.")
    return plan_output


def _artifact_payload(label: str, url: str) -> str:
    return json.dumps({"filename": label, "url": url})


def _artifact_refs_from_content(content: str) -> list[dict[str, str]]:
    return [
        {"label": label, "url": url, "artifact_type": "file"}
        for label, url in _extract_storage_markdown_links(content or "")
    ]


def _build_specialist_capability_result(
    *,
    route: str,
    content: str,
    error: bool,
    handoff_required: bool = False,
    metadata: dict[str, Any] | None = None,
) -> CapabilityResult:
    capability = get_capability_by_route(route) or {}
    capability_id = capability.get("capability_id") or route
    output_type = capability.get("output_type") or "text"
    normalized_content = content or ""
    return CapabilityResult(
        capability_id=capability_id,
        route=route,
        status="awaiting_clarification" if handoff_required else ("failed" if error else "completed"),
        output_type=output_type,
        content=normalized_content,
        artifacts=_artifact_refs_from_content(normalized_content),
        handoff_required=handoff_required,
        error_text=normalized_content if error else None,
        metadata=metadata or {},
    )


def _validation_summary_for_context(validation_result: ValidationResultContract) -> str:
    issues = "; ".join(issue.message for issue in validation_result.issues[:2])
    suffix = f" Achados: {issues}" if issues else ""
    return f"[Validação {validation_result.validator_id} - {validation_result.status}] {validation_result.summary}{suffix}"


async def _log_workflow_stages(
    execution_logger,
    execution_id: str | None,
    *,
    workflow_id: str,
    stages: list,
    message: str,
) -> None:
    if not execution_logger or not execution_id:
        return
    await execution_logger.log_event(
        execution_id,
        event_type="workflow_stage_snapshot",
        message=message,
        raw_payload={
            "workflow_id": workflow_id,
            "stages": [stage.model_dump() for stage in stages],
        },
    )


async def _log_policy_decision(
    execution_logger,
    execution_id: str | None,
    *,
    execution_agent_id: str | None = None,
    decision: PolicyDecisionContract,
) -> None:
    if not execution_logger or not execution_id:
        return
    await execution_logger.log_event(
        execution_id,
        execution_agent_id=execution_agent_id,
        level="warning" if (decision.request_clarification or decision.retry_same_route or decision.continue_partial) else "info",
        event_type="workflow_policy_decision",
        message=decision.user_message,
        raw_payload=decision.model_dump(),
    )


async def _log_replan_decision(
    execution_logger,
    execution_id: str | None,
    *,
    execution_agent_id: str | None = None,
    decision: RouteReplanDecisionContract,
) -> None:
    if not execution_logger or not execution_id:
        return
    await execution_logger.log_event(
        execution_id,
        execution_agent_id=execution_agent_id,
        level="warning",
        event_type="step_replanned",
        message=decision.user_message,
        raw_payload=decision.model_dump(),
    )


async def _log_pipeline_terminated(
    execution_logger,
    execution_id: str | None,
    *,
    route: str,
    step: int | None = None,
    total_steps: int | None = None,
    accumulated_context_chars: int | None = None,
    artifact_only: bool = False,
    skipped_steps: list[int] | None = None,
) -> None:
    if not execution_logger:
        return
    message = (
        f"Pipeline encerrado no step {step}/{total_steps} ({route})."
        if step is not None and total_steps is not None
        else f"Pipeline encerrado ({route})."
    )
    payload: dict[str, Any] = {"terminal_route": route}
    if step is not None:
        payload["terminal_step"] = step
    if total_steps is not None:
        payload["total_steps"] = total_steps
    if accumulated_context_chars is not None:
        payload["accumulated_context_chars"] = accumulated_context_chars
    if skipped_steps is not None:
        payload["skipped_steps"] = skipped_steps
    if artifact_only:
        payload["artifact_only"] = True
    await execution_logger.log_event(
        execution_id,
        event_type="pipeline_terminated",
        message=message,
        raw_payload=payload,
    )


async def _emit_policy_clarification(
    *,
    decision: PolicyDecisionContract,
    execution_logger,
    execution_id: str | None,
    execution_agent_id: str | None = None,
) -> AsyncGenerator[str, None]:
    if not decision.clarification_questions:
        return
    questions_payload = [q.model_dump() for q in decision.clarification_questions]
    yield sse("clarification", json.dumps(questions_payload))
    if execution_logger and execution_id:
        await execution_logger.log_event(
            execution_id,
            execution_agent_id=execution_agent_id,
            event_type="clarification_requested",
            message=decision.user_message,
            raw_payload={"questions": questions_payload, "decision": decision.model_dump()},
        )
        await execution_logger.finish_execution(execution_id, status="awaiting_clarification")


async def _emit_file_artifacts(content: str) -> AsyncGenerator[str, None]:
    md_links = _extract_storage_markdown_links(content)
    if not md_links:
        return

    for label, url in md_links:
        yield sse("file_artifact", _artifact_payload(label, url))


def _looks_like_design_html(content: str) -> bool:
    trimmed = (content or "").strip()
    if not trimmed:
        return False
    return trimmed.startswith("<!DOCTYPE") or trimmed.lower().startswith("<html")


def _extract_design_html(content: str) -> str | None:
    trimmed = (content or "").strip()
    if not trimmed:
        return None
    if _looks_like_design_html(trimmed):
        return trimmed
    fenced_match = re.match(r"```(?:html)?\s*([\s\S]*?)\s*```$", trimmed, re.IGNORECASE)
    if fenced_match:
        inner = fenced_match.group(1).strip()
        if _looks_like_design_html(inner):
            return inner
    return None


_VISUAL_SKILL_BLOCK_RE = re.compile(
    r"\[Passo \d+ - (?P<route>slide_generator|static_design_generator)\]: (?P<content>.*?)(?=\n\[Passo \d+ - |\Z)",
    re.DOTALL,
)


def _extract_visual_context_for_design(accumulated_context: str) -> str:
    if not accumulated_context:
        return ""
    matches = list(_VISUAL_SKILL_BLOCK_RE.finditer(accumulated_context))
    if matches:
        content = matches[-1].group("content").strip()
        if content:
            return content
    return accumulated_context


def _extract_template_payload_from_messages(messages: list[dict]) -> str:
    for message in reversed(messages or []):
        content = message.get("content")
        if isinstance(content, str):
            trimmed = content.strip()
            if trimmed.startswith("{") and '"template_id"' in trimmed:
                return trimmed
    return ""


def _extract_template_payload_from_any_messages(messages: list[dict]) -> str:
    for message in reversed(messages or []):
        content = message.get("content")
        if isinstance(content, str):
            trimmed = content.strip()
            if trimmed.startswith("{") and '"template_id"' in trimmed:
                return trimmed
    return ""


def _truncate_semantic_text(text: str, *, max_chars: int = _MAX_CONTEXT_ENTRY_CHARS) -> str:
    normalized = (text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    head = max(600, int(max_chars * 0.35))
    tail = max(900, max_chars - head - 80)
    return (
        normalized[:head].rstrip()
        + "\n\n...[conteúdo intermediário compactado para preservar contexto]...\n\n"
        + normalized[-tail:].lstrip()
    )


def _compact_context_entry(*, route: str, content: Any) -> str:
    text = str(content or "").strip()
    if not text:
        return ""

    if route == "validation":
        return _truncate_semantic_text(text, max_chars=1200)

    if route == "design_generator" or _looks_like_design_html(text):
        title = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
        title_text = title.group(1).strip() if title else "Design gerado"
        return f"Artefato visual gerado: {title_text}."

    if route == "session_file":
        return _truncate_semantic_text(text, max_chars=2200)

    if route == "web_search":
        urls = _extract_source_urls_from_text(text)
        summary_match = _SEARCH_SUMMARY_CONTEXT_PATTERN.search(text)
        summary = summary_match.group(1).strip() if summary_match else text
        compact = _truncate_semantic_text(summary, max_chars=1800)
        if urls:
            compact += "\n\nFontes principais:\n" + "\n".join(urls[:5])
        return compact

    if route == "python":
        file_links = _extract_storage_markdown_links(text)
        if file_links:
            links_only = "\n".join(f"[{label}]({url})" for label, url in file_links[:5])
            return f"Python gerou artefatos:\n{links_only}"
        return _truncate_semantic_text(text, max_chars=2200)

    if route == "browser":
        return _truncate_semantic_text(text, max_chars=1800)

    if route == "spy_pages":
        return _truncate_semantic_text(text, max_chars=1800)

    if route == "file_modifier":
        file_links = _extract_storage_markdown_links(text)
        if file_links:
            return "Arquivo modificado com sucesso:\n" + "\n".join(f"[{label}]({url})" for label, url in file_links[:5])
        return _truncate_semantic_text(text, max_chars=1800)

    return _truncate_semantic_text(text, max_chars=_MAX_CONTEXT_ENTRY_CHARS)


def _clamp_accumulated_context(text: str) -> str:
    normalized = text or ""
    if len(normalized) <= _MAX_ACCUMULATED_CONTEXT_CHARS:
        return normalized
    head = 3000
    tail = _MAX_ACCUMULATED_CONTEXT_CHARS - head - 90
    return (
        normalized[:head].rstrip()
        + "\n\n...[contexto intermediário compactado para manter foco operacional]...\n\n"
        + normalized[-tail:].lstrip()
    )


def _append_to_accumulated_context(
    accumulated_context: str,
    *,
    step: int,
    route: str,
    content: Any,
    error: bool = False,
) -> str:
    label = f"ERRO {route}" if error else route
    compact = _compact_context_entry(route=route, content=content)
    entry = f"\n[Passo {step} - {label}]: {compact}"
    return _clamp_accumulated_context(accumulated_context + entry)


def _render_local_design_if_possible(raw_context: str) -> str | None:
    if not raw_context:
        return None
    try:
        from backend.services.design_template_renderer import parse_template_payload, render_design_template_from_context
        payload = parse_template_payload(raw_context)
        if payload:
            render_mode = str(payload.get("render_mode") or "").strip().lower()
            if render_mode and render_mode != "deterministic":
                return None
        return render_design_template_from_context(raw_context)
    except Exception:
        logger.exception("[ORCHESTRATOR] Falha ao renderizar design determinístico local.")
        return None


async def _emit_design_artifact(content: str) -> AsyncGenerator[str, None]:
    html = _extract_design_html(content)
    if not html:
        return

    designs = [part.strip() for part in html.split("<!-- ARCCO_DESIGN_SEPARATOR -->") if part.strip()]
    if not designs:
        return

    yield sse("design_artifact", json.dumps({"designs": designs}))


async def _stream_assistant_text(messages: list, model: str) -> AsyncGenerator[str, None]:
    accumulated = ""
    async for chunk in stream_openrouter(
        messages=messages,
        model=model,
        max_tokens=4096,
        temperature=0.7,
    ):
        if "choices" not in chunk or not chunk["choices"]:
            continue
        delta = chunk["choices"][0].get("delta", {})
        content = delta.get("content")
        if not content:
            continue
        accumulated += content
        yield sse("chunk", content)

    if not accumulated:
        yield sse("chunk", "Desculpe, não consegui gerar uma resposta. Tente novamente.")


async def _yield_text_chunks(content: str, chunk_size: int = 40) -> AsyncGenerator[str, None]:
    text = content or "Desculpe, não consegui gerar uma resposta. Tente novamente."
    for i in range(0, len(text), chunk_size):
        yield sse("chunk", text[i:i + chunk_size])


async def _generate_consolidated_response(
    *,
    supervisor_prompt: str,
    supervisor_model: str,
    session_inventory_message: str,
    user_intent: str,
    accumulated_context: str,
    had_failures: bool,
    failure_summaries: list[str],
) -> str:
    failure_block = ""
    if had_failures and failure_summaries:
        failure_block = "\n\nFalhas verificadas durante a execução:\n- " + "\n- ".join(failure_summaries)
    final_prompt = [
        {"role": "system", "content": supervisor_prompt},
        *(
            [{"role": "system", "content": session_inventory_message}]
            if session_inventory_message
            else []
        ),
        {
            "role": "user",
            "content": (
                f"Pedido inicial: {user_intent}\n\n"
                "Use apenas os resultados validados abaixo para redigir a resposta final ao utilizador. "
                "Se houve falhas, admita a limitação com clareza e NÃO invente fatos, links, valores, conteúdos de arquivos, "
                "resultados de pesquisa, nem chame ferramentas. NÃO devolva JSON, pseudo-tool-calls ou instruções internas.\n\n"
                f"Resultados validados:\n{accumulated_context or 'Nenhum resultado validado disponível.'}"
                f"{failure_block}"
            ),
        },
    ]
    data = await _call_openrouter_with_timeout(
        timeout=_SUPERVISOR_TIMEOUT,
        label="consolidação final",
        messages=final_prompt,
        model=supervisor_model,
        max_tokens=4096,
        temperature=0.2,
    )
    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    return _sanitize_user_facing_response(content, had_failures=had_failures)


async def _resume_browser_handoff(
    *,
    messages: list,
    browser_resume_token: str,
    user_id: str | None,
    supervisor_prompt: str,
    supervisor_model: str,
    execution_id: str | None,
    execution_logger,
) -> AsyncGenerator[str, None]:
    paused = get_paused_browser_session(browser_resume_token)
    if not paused:
        yield sse("error", "A sessão pausada do navegador expirou ou não foi encontrada.")
        return

    resume_url = str(paused.get("url") or "")
    func_args = {
        "url": resume_url,
        "goal": paused.get("goal") or "",
        "mobile": bool(paused.get("mobile", False)),
        "include_tags": paused.get("include_tags"),
        "exclude_tags": paused.get("exclude_tags"),
        "resume_token": browser_resume_token,
    }

    yield sse("steps", "<step>Retomando sessão do navegador...</step>")
    yield sse("browser_action", json.dumps({
        "status": "navigating",
        "url": resume_url,
        "title": "Retomando a sessão ao vivo...",
        "actions": [],
    }))

    browser_agent_id = None
    if execution_logger:
        browser_agent_id = await execution_logger.start_agent(
            execution_id,
            agent_key="browser",
            agent_name="browser",
            model=registry.get_model("planner") or supervisor_model,
            role="tool",
            route="browser_resume",
            input_payload={"func_args": func_args, "resume": True},
        )

    specialist_result = None
    handoff_exc = None
    async for event in _exec_browser_with_progress(func_args, user_id=user_id, timeout=_BROWSER_TIMEOUT):
        if isinstance(event, dict) and "_result" in event:
            if event.get("_timeout"):
                specialist_result = f"Erro: Timeout de {int(_BROWSER_TIMEOUT)}s ao retomar {resume_url}. O site pode estar lento ou inacessível."
            elif event.get("_error"):
                specialist_result = f"Erro ao retomar Browser Agent: {event['_error']}"
            else:
                specialist_result = event["_result"]
        elif isinstance(event, dict) and "_handoff" in event:
            handoff_exc = event["_handoff"]
        else:
            yield event

    if handoff_exc is not None:
        payload = _browser_handoff_payload(handoff_exc, resume_url)
        workflow_handoff = build_browser_handoff_state(payload=payload, resume_token=handoff_exc.resume_token)
        yield sse("browser_action", json.dumps(payload["browser_action"]))
        yield sse("needs_clarification", json.dumps(payload))
        if execution_logger:
            await execution_logger.log_event(
                execution_id,
                execution_agent_id=browser_agent_id,
                level="warning",
                event_type="browser_handoff_requested",
                message=handoff_exc.message,
                tool_name="ask_browser",
                tool_args=func_args,
                raw_payload={
                    **payload,
                    "workflow_handoff": workflow_handoff.model_dump() if workflow_handoff else None,
                },
            )
            await execution_logger.finish_agent(
                browser_agent_id,
                status="awaiting_clarification",
                output_payload={"preview": handoff_exc.message},
                metadata={"resume_token": handoff_exc.resume_token},
            )
            await _log_workflow_stages(
                execution_logger,
                execution_id,
                workflow_id="browser_workflow",
                stages=build_browser_workflow_stages(
                    awaiting_handoff=True,
                    completed=False,
                    resume_token=handoff_exc.resume_token,
                    url=resume_url,
                ),
                message="Workflow do navegador aguardando handoff humano",
            )
            yield sse(
                "workflow_state",
                json.dumps(
                    {
                        "workflow_id": "browser_workflow",
                        "stages": [
                            stage.model_dump()
                            for stage in build_browser_workflow_stages(
                                awaiting_handoff=True,
                                completed=False,
                                resume_token=handoff_exc.resume_token,
                                url=resume_url,
                            )
                        ],
                        "message": "Workflow do navegador aguardando handoff humano",
                    }
                ),
            )
        return

    if specialist_result is None:
        specialist_result = f"Erro: browser não retornou resultado para {resume_url}."

    if execution_logger:
        await execution_logger.log_event(
            execution_id,
            execution_agent_id=browser_agent_id,
            event_type="tool_result",
            message=f"Browser retomado para {resume_url[:120]}",
            tool_name="ask_browser",
            tool_args=func_args,
            tool_result=str(specialist_result)[:2000],
            raw_payload={
                "workflow_state": {
                    "status": "completed" if not str(specialist_result).startswith("Erro") else "failed",
                    "url": resume_url,
                    "resume_token": browser_resume_token,
                }
            },
        )
        await execution_logger.finish_agent(
            browser_agent_id,
            status="completed" if not str(specialist_result).startswith("Erro") else "failed",
            output_payload={"preview": str(specialist_result)[:2000]},
            error_text=str(specialist_result) if str(specialist_result).startswith("Erro") else None,
        )
        await _log_workflow_stages(
            execution_logger,
            execution_id,
            workflow_id="browser_workflow",
            stages=build_browser_workflow_stages(
                awaiting_handoff=False,
                completed=not str(specialist_result).startswith("Erro"),
                resume_token=browser_resume_token,
                url=resume_url,
            ),
            message="Workflow do navegador retomado",
        )
        yield sse(
            "workflow_state",
            json.dumps(
                {
                    "workflow_id": "browser_workflow",
                    "stages": [
                        stage.model_dump()
                        for stage in build_browser_workflow_stages(
                            awaiting_handoff=False,
                            completed=not str(specialist_result).startswith("Erro"),
                            resume_token=browser_resume_token,
                            url=resume_url,
                        )
                    ],
                    "message": "Workflow do navegador retomado",
                }
            ),
        )

    if str(specialist_result).startswith("Erro"):
        yield sse("browser_action", json.dumps({
            "status": "error",
            "url": resume_url,
            "title": str(specialist_result)[:100],
        }))
        yield sse("error", str(specialist_result))
        return

    yield sse("browser_action", json.dumps({
        "status": "done",
        "url": resume_url,
        "title": "Sessão retomada com sucesso",
    }))
    yield sse("steps", "<step>Navegação retomada — redigindo a resposta final...</step>")

    response_messages = [
        {"role": "system", "content": supervisor_prompt},
        *messages,
        {
            "role": "system",
            "content": (
                "O navegador retomou uma sessão pausada e concluiu a coleta. "
                "Responda ao usuário final com base nesse resultado. "
                "Não mencione arquitetura interna nem peça para repetir a ação humana."
            ),
        },
        {
            "role": "user",
            "content": f"Resultado do navegador retomado:\n\n{specialist_result}",
        },
    ]
    async for event in _stream_assistant_text(response_messages, supervisor_model):
        yield event


async def _call_supervisor_for_step(
    step_messages: list,
    supervisor_model: str,
    tool_choice,
    tools: list,
    forced_tool_name: str | None = None,
) -> dict:
    """
    Executa a chamada do supervisor para um passo do planner.

    Comportamentos adaptativos:
    - Se o modelo está cacheado como "sem suporte a tool_choice forçado", vai direto para
      tool_choice='auto' sem tentar e falhar (zero overhead após primeira descoberta).
    - Se a chamada falha com 404/"tool_choice", registra no cache e retenta com "auto".
    - Se o modelo ignora o tool_choice mas responde em texto, reforça via instrução.
    - Se o modelo não suporta tools algum, registra e lança erro informativo.
    """
    from backend.core.model_capabilities import (
        supports_forced_tool_choice,
        mark_no_forced_tool_choice,
        supports_tools,
        mark_no_tools,
    )

    # Se já sabemos que o modelo não suporta forced tool_choice, vai direto para "auto"
    effective_tool_choice = tool_choice
    if forced_tool_name and not supports_forced_tool_choice(supervisor_model):
        effective_tool_choice = "auto"
        logger.debug(
            "[ORCHESTRATOR] '%s' → tool_choice='auto' (capacidade cacheada)", supervisor_model
        )

    def _build_forced_instruction_messages(base: list) -> list:
        """Adiciona instrução textual para guiar modelo sem tool_choice forçado."""
        if not forced_tool_name:
            return base
        return base + [{
            "role": "system",
            "content": (
                f"Você DEVE responder chamando exclusivamente a ferramenta '{forced_tool_name}'. "
                "Não responda em texto livre."
            ),
        }]

    def _is_tool_choice_error(err: Exception) -> bool:
        s = str(err)
        return "tool_choice" in s and ("No endpoints found" in s or "404" in s)

    def _is_no_tools_error(err: Exception) -> bool:
        s = str(err).lower()
        return ("tool" in s or "function" in s) and (
            "not support" in s or "unsupported" in s or "invalid" in s
        ) and "tool_choice" not in str(err)

    try:
        data = await _call_openrouter_with_timeout(
            timeout=_SUPERVISOR_TIMEOUT,
            label=f"Supervisor ({supervisor_model})",
            messages=_build_forced_instruction_messages(step_messages) if effective_tool_choice == "auto" else step_messages,
            model=supervisor_model,
            max_tokens=4096,
            tools=tools,
            tool_choice=effective_tool_choice,
        )
    except Exception as e:
        if _is_tool_choice_error(e):
            # Modelo não suporta tool_choice forçado — aprender e retentar
            mark_no_forced_tool_choice(supervisor_model)
            logger.warning(
                "[ORCHESTRATOR] '%s' não suporta tool_choice forçado → fallback 'auto'.",
                supervisor_model,
            )
            data = await _call_openrouter_with_timeout(
                timeout=_SUPERVISOR_TIMEOUT,
                label=f"Supervisor ({supervisor_model})",
                messages=_build_forced_instruction_messages(step_messages),
                model=supervisor_model,
                max_tokens=4096,
                tools=tools,
                tool_choice="auto",
            )
        elif _is_no_tools_error(e):
            # Modelo sem suporte a function calling — registrar e informar
            mark_no_tools(supervisor_model)
            raise Exception(
                f"O modelo '{supervisor_model}' não suporta function calling. "
                "Troque o modelo do agente 'chat' no painel admin → Orquestração."
            )
        else:
            raise

    message = data["choices"][0]["message"]

    # Se esperávamos um tool_call mas o modelo respondeu em texto mesmo com "auto"
    if forced_tool_name and not message.get("tool_calls"):
        logger.warning(
            "[ORCHESTRATOR] '%s' ignorou tool_choice forçado '%s'. Reforçando instrução.",
            supervisor_model,
            forced_tool_name,
        )
        retry_messages = _build_forced_instruction_messages(step_messages)
        retry_tool_choice = "auto" if not supports_forced_tool_choice(supervisor_model) else tool_choice
        try:
            retry = await _call_openrouter_with_timeout(
                timeout=_SUPERVISOR_TIMEOUT,
                label=f"Supervisor ({supervisor_model})",
                messages=retry_messages,
                model=supervisor_model,
                max_tokens=4096,
                tools=tools,
                tool_choice=retry_tool_choice,
            )
        except Exception as e:
            if _is_tool_choice_error(e):
                mark_no_forced_tool_choice(supervisor_model)
                retry = await _call_openrouter_with_timeout(
                    timeout=_SUPERVISOR_TIMEOUT,
                    label=f"Supervisor ({supervisor_model})",
                    messages=retry_messages,
                    model=supervisor_model,
                    max_tokens=4096,
                    tools=tools,
                    tool_choice="auto",
                )
            else:
                raise
        message = retry["choices"][0]["message"]

    return message


def _build_session_inventory_message(session_id: str | None) -> str | None:
    if not session_id:
        return None

    try:
        from backend.services.session_file_service import get_session_inventory, touch_session

        touch_session(session_id)
        inventory = get_session_inventory(session_id)
        if not inventory:
            return f"Arquivos anexados nesta sessão ({session_id}): nenhum arquivo disponível."

        items = ", ".join(
            f"{item['file_name']} ({item['status']})"
            for item in inventory
            if item.get("file_name")
        )
        return (
            f"Arquivos anexados nesta sessão ({session_id}): {items}. "
            "Consulte o conteúdo desses anexos EXCLUSIVAMENTE com a ferramenta read_session_file."
        )
    except Exception as exc:
        logger.error("Falha ao montar inventário da sessão %s: %s", session_id, exc)
        return None


# ── Guardrails de Saída ──────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'>]+', re.IGNORECASE)
_DOC_TAG_RE = re.compile(r'<doc\s+title="([^"]+)">([\s\S]*?)</doc>', re.DOTALL)


def _extract_urls_from_tool_history(messages: list) -> list[str]:
    """
    Extrai URLs de download do histórico de tool results.
    Isso funciona independente do que o LLM decidir dizer —
    os links gerados pelo executor (Supabase upload) são determinísticos.
    """
    urls = []
    for msg in messages:
        if msg.get("role") == "tool":
            content = str(msg.get("content", ""))
            md_links = _MARKDOWN_LINK_PATTERN.findall(content)
            if md_links:
                urls.extend(url for _, url in md_links)
            else:
                raw_urls = _URL_PATTERN.findall(content)
                urls.extend(url for url in raw_urls if 'supabase' in url or 'storage' in url)
    return urls


def _validate_specialist_response(response: str, route: str, tool_messages: list) -> str:
    """
    Valida e corrige a resposta do especialista.
    Se a rota exige link de download e o LLM alucinhou (não incluiu), injeta o link real.
    """
    if not route_requires_link_only(route):
        return response

    has_link = bool(_MARKDOWN_LINK_PATTERN.search(response))
    if has_link:
        return response

    urls = _extract_urls_from_tool_history(tool_messages)
    if urls:
        url = urls[-1]
        ext = url.rsplit('.', 1)[-1].split('?')[0].upper() if '.' in url else 'Arquivo'
        link_label = f"Baixar {ext}" if ext in ('PDF', 'XLSX', 'PPTX', 'DOCX') else "Baixar Arquivo"
        logger.warning(f"[ANTI-HALLUCINATION] Especialista não incluiu link. Injetando: {url[:60]}...")
        response += f"\n\n[{link_label}]({url})"
    else:
        logger.error(f"[ANTI-HALLUCINATION] Nenhum link encontrado nos tool results para rota '{route}'")

    return response


# ── Loops dos Especialistas (Sub-Agentes) ────────────────────────────────────

async def _run_specialist_with_tools(
    messages: list,
    model: str,
    system_prompt: str,
    tools: list,
    user_id: str | None = None,
    max_iterations: int = 5,
    thought_log: list | None = None,
    tool_history: list | None = None,
) -> str:
    """
    Executa especialista com ferramentas. Retorna resposta final como string.
    Se thought_log for passado, acumula nele o raciocínio do especialista.
    """
    current = [{"role": "system", "content": system_prompt}, *messages]

    for _ in range(max_iterations):
        data = await _call_openrouter_with_timeout(
            timeout=_SPECIALIST_TIMEOUT,
            label=f"Especialista ({model})",
            messages=current,
            model=model,
            max_tokens=4096,
            tools=tools if tools else None,
        )
        message = data["choices"][0]["message"]
        current.append(message)

        if message.get("tool_calls"):
            if thought_log is not None:
                intermediate_thought = (message.get("content") or "").strip()
                if intermediate_thought:
                    thought_log.append(intermediate_thought)

            for tool in message["tool_calls"]:
                func_name = tool["function"]["name"]
                try:
                    func_args = json.loads(tool["function"]["arguments"])
                    result = await execute_tool(func_name, func_args, user_id=user_id)
                except json.JSONDecodeError:
                    result = "Erro: Argumentos da ferramenta com JSON inválido. Corrija a formatação JSON e tente novamente."
                except Exception as e:
                    result = f"Erro na execução da ferramenta: {e}"

                current.append({
                    "role": "tool",
                    "tool_call_id": tool["id"],
                    "content": str(result),
                })
                if tool_history is not None:
                    tool_history.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": str(result),
                    })
        else:
            return message.get("content", "")

    return "Limite de iterações atingido no Especialista."


async def _run_terminal_one_shot(
    messages: list,
    model: str,
    system_prompt: str,
    tools: list,
    user_id: str | None = None,
) -> str:
    """
    Agente terminal com suporte a UMA chamada de ferramenta.
    Fluxo otimizado (evita a 3ª chamada ao LLM).
    """
    current = [{"role": "system", "content": system_prompt}, *messages]

    data = await _call_openrouter_with_timeout(
        timeout=_TERMINAL_TIMEOUT,
        label=f"Terminal ({model})",
        messages=current,
        model=model,
        max_tokens=6000,
        tools=tools if tools else None,
    )
    message = data["choices"][0]["message"]

    if not message.get("tool_calls"):
        return message.get("content", "")

    tool = message["tool_calls"][0]
    func_name = tool["function"]["name"]
    try:
        func_args = json.loads(tool["function"]["arguments"])
        result = await execute_tool(func_name, func_args, user_id=user_id)
    except json.JSONDecodeError:
        result = "Erro: argumentos JSON inválidos na ferramenta. Tente novamente."
    except Exception as e:
        result = f"Erro ao executar '{func_name}': {e}"

    return result


async def _run_guarded_specialist(
    route: str,
    user_intent: str,
    temp_messages: list,
    model: str,
    custom_step_msg: str,
    user_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Executa o especialista com guardrails internos de consistência.
    Yields SSE steps para a UI, e no final yielda 'RESULT:' com a resposta validada.
    """
    specialist_response = ""
    tool_history: list[dict[str, str]] = []
    yield sse("steps", f"<step>{custom_step_msg}</step>")

    thought_log: list[str] = []
    try:
        specialist_response = await _run_specialist_with_tools(
            list(temp_messages),
            registry.get_model(route) or model,
            registry.get_prompt(route),
            registry.get_tools(route),
            user_id=user_id,
            thought_log=thought_log,
            tool_history=tool_history,
        )
    except Exception as e:
        logger.error(f"[SPECIALIST] Erro na execução do especialista '{route}': {e}")
        yield f"RESULT:Erro ao processar especialista: {e}"
        return

    for thought in thought_log:
        yield sse("thought", thought)

    specialist_response = _validate_specialist_response(
        specialist_response, route, tool_history
    )

    yield f"RESULT:{specialist_response}"


# ── Pipeline Principal (Supervisor ReAct) ────────────────────────────────────

async def orchestrate_and_stream(
    messages: list,
    model: str,
    session_id: str | None = None,
    user_id: str | None = None,
    browser_resume_token: str | None = None,
    spy_pages_enabled: bool = False,
    execution_id: str | None = None,
    execution_logger = None,
) -> AsyncGenerator[str, None]:
    """
    Pipeline ReAct (Supervisor-Worker) + Roteamento Dinâmico.
    1. Executa o Planner para gerar um plano determinístico JSON.
    2. Itera sobre o plano se for complexo.
       - Passa o `step_context` (resultado do passo anterior) para cada passo logando com clareza.
    """

    from backend.agents.planner import generate_plan

    supervisor_prompt = registry.get_prompt("chat")
    supervisor_model = registry.get_model("chat") or model
    session_inventory_message = _build_session_inventory_message(session_id)
    session_inventory_items = _get_session_inventory_items(session_id)

    # Extrai o intent antes de tudo — necessário para filtro de skills
    user_intent = next(
        (str(m["content"]) for m in reversed(messages) if m.get("role") == "user"), ""
    )
    precondition_check = evaluate_preconditions(
        user_intent=user_intent,
        session_items=session_inventory_items,
    )

    # Para o planner, constrói contexto completo em conversas multi-turno.
    # Ex: quando o usuário responde uma clarificação ("10 slides sobre marketing"),
    # o planner precisa saber o pedido original para gerar o plano correto.
    _user_msgs_count = sum(1 for m in messages if m.get("role") == "user")
    if _user_msgs_count > 1:
        _recent = messages[-8:] if len(messages) > 8 else messages
        _parts = []
        for m in _recent:
            _role = m.get("role", "")
            _content = str(m.get("content", "")).strip()
            if _role == "user" and _content:
                _parts.append(f"[Usuário]: {_content}")
            elif _role == "assistant" and _content:
                _parts.append(f"[Assistente]: {_content[:400]}")
        _planner_intent = "\n".join(_parts)
    else:
        _planner_intent = user_intent

    # Monta tools dinamicamente (inclui Computer, Spy Pages e Skills dinâmicas se disponíveis)
    # Skills são filtradas por relevância ao intent do usuário — evita injetar 70 skills desnecessárias
    active_tools = (
        SUPERVISOR_TOOLS
        + (SPY_PAGES_TOOLS if spy_pages_enabled else [])
        + skills_loader.get_skill_tool_definitions(user_intent)
    )
    if spy_pages_enabled:
        supervisor_prompt += (
            "\n\nO usuário ativou o Spy Pages. Use a ferramenta analyze_web_pages para analisar tráfego, "
            "métricas de engajamento e concorrentes dos sites solicitados. Passe as URLs exatamente como "
            "o usuário forneceu."
        )

    planner_model = registry.get_model("planner") or supervisor_model

    if browser_resume_token:
        async for event in _resume_browser_handoff(
            messages=messages,
            browser_resume_token=browser_resume_token,
            user_id=user_id,
            supervisor_prompt=supervisor_prompt,
            supervisor_model=supervisor_model,
            execution_id=execution_id,
            execution_logger=execution_logger,
        ):
            yield event
        return

    # ── Step inicial contextual — responde imediatamente ao usuário ──
    _short_intent = user_intent[:80].rstrip("., !?")
    yield sse("steps", f"<step>Entendendo o pedido: {_short_intent}...</step>")

    if execution_logger:
        await execution_logger.log_event(
            execution_id,
            event_type="execution_started",
            message="Orquestração iniciada",
            raw_payload={"session_id": session_id, "model": model},
        )
        await execution_logger.log_event(
            execution_id,
            event_type="preconditions_evaluated",
            message=precondition_check.summary,
            raw_payload=precondition_check.model_dump(),
        )

    if precondition_check.status == "clarification_required" and precondition_check.questions:
        yield sse("pre_action", precondition_check.summary)
        questions_payload = [q.model_dump() for q in precondition_check.questions]
        yield sse("clarification", json.dumps(questions_payload))
        if execution_logger:
            await execution_logger.log_event(
                execution_id,
                event_type="clarification_requested",
                message=f"Aguardando clarificação do usuário ({len(precondition_check.questions)} perguntas)",
                raw_payload={
                    "questions": questions_payload,
                    "task_type": precondition_check.task_type,
                    "execution_engine": precondition_check.execution_engine,
                    "preconditions": precondition_check.model_dump(),
                },
            )
            await execution_logger.finish_execution(
                execution_id,
                status="awaiting_clarification",
                metadata={
                    "task_type": precondition_check.task_type,
                    "execution_engine": precondition_check.execution_engine,
                    "preconditions": precondition_check.model_dump(),
                },
            )
        return

    # ── 1. Planejamento (Planner Output Estruturado — modelo leve) ──
    yield sse("steps", "<step>Definindo estratégia de execução...</step>")
    planner_agent_id = None
    if execution_logger:
        planner_agent_id = await execution_logger.start_agent(
            execution_id,
            agent_key="planner",
            agent_name="Planejador de Execução",
            model=planner_model,
            role="planner",
            route="generate_plan",
            input_payload={"user_intent": user_intent},
        )
    plan_output = await generate_plan(_planner_intent, planner_model)
    plan_output = _normalize_plan_for_session_files(
        plan_output,
        user_intent=user_intent,
        session_id=session_id,
    )
    plan_output = _normalize_plan_for_visual_requests(
        plan_output,
        user_intent=user_intent,
    )
    plan_output = _normalize_plan_for_mass_document_requests(
        plan_output,
        user_intent=user_intent,
        session_id=session_id,
    )
    plan_output = _normalize_plan_for_open_problem_solving(
        plan_output,
        user_intent=user_intent,
        session_id=session_id,
    )
    plan_output = _reconcile_plan_clarification_with_inventory(
        plan_output,
        session_id=session_id,
    )
    inferred_task_type = getattr(plan_output, "task_type", None) or infer_task_type(user_intent, plan_output.steps)
    plan_output.task_type = inferred_task_type
    task_type_definition = get_task_type_definition(inferred_task_type) or {}
    execution_engine = resolve_execution_engine(inferred_task_type, plan_output.steps)
    mass_doc_handoff = None
    mass_doc_stages = None
    open_solver_context = None
    open_solver_stages = None
    if inferred_task_type == "mass_document_analysis":
        mass_doc_items = _get_session_inventory_items(session_id)
        mass_doc_handoff = build_mass_document_handoff(
            session_items=mass_doc_items,
            user_intent=user_intent,
        )
        mass_doc_stages = build_mass_document_stages(
            session_items=mass_doc_items,
            awaiting_user_goal=bool(plan_output.needs_clarification),
            delivery_completed=False,
        )
    elif inferred_task_type == "open_problem_solving":
        open_solver_items = _get_session_inventory_items(session_id)
        open_solver_context = init_open_solver_context(
            user_intent=user_intent,
            session_items=open_solver_items,
            step_budget=max(len(plan_output.steps), 1) + 2,
        )
        open_solver_stages = build_open_solver_stages(
            awaiting_user_goal=bool(plan_output.needs_clarification),
            delivery_completed=False,
            steps_used=0,
            step_budget=int(open_solver_context.get("step_budget") or 0),
        )
    if execution_logger:
        await execution_logger.log_event(
            execution_id,
            event_type="execution_context_initialized",
            message=f"Tarefa classificada como {inferred_task_type}",
            raw_payload={
                "task_type": inferred_task_type,
                "execution_engine": execution_engine,
                "task_type_definition": task_type_definition,
                "step_count": len(plan_output.steps),
            },
        )
        await execution_logger.log_event(
            execution_id,
            event_type="strategy_selected",
            message=f"Estratégia principal selecionada: {execution_engine}",
            raw_payload={
                "task_type": inferred_task_type,
                "execution_engine": execution_engine,
                "step_count": len(plan_output.steps),
                "preconditions": precondition_check.model_dump(),
            },
        )
        if mass_doc_handoff:
            await execution_logger.log_event(
                execution_id,
                event_type="step_handoff_prepared",
                message=mass_doc_handoff.summary,
                raw_payload=mass_doc_handoff.model_dump(),
            )
        if mass_doc_stages:
            await _log_workflow_stages(
                execution_logger,
                execution_id,
                workflow_id="mass_document_analysis",
                stages=mass_doc_stages,
                message="Pipeline documental inicializado",
            )
            yield sse(
                "workflow_state",
                json.dumps(
                    {
                        "workflow_id": "mass_document_analysis",
                        "stages": [stage.model_dump() for stage in mass_doc_stages],
                        "message": "Pipeline documental inicializado",
                    }
                ),
            )
        if open_solver_context and open_solver_stages:
            await execution_logger.log_event(
                execution_id,
                event_type="open_solver_initialized",
                message="Modo open problem solver inicializado",
                raw_payload={
                    "scratchpad": open_solver_context,
                    "workflow_id": "open_problem_solving",
                },
            )
            await _log_workflow_stages(
                execution_logger,
                execution_id,
                workflow_id="open_problem_solving",
                stages=open_solver_stages,
                message="Open solver inicializado",
            )
            yield sse(
                "workflow_state",
                json.dumps(
                    {
                        "workflow_id": "open_problem_solving",
                        "stages": [stage.model_dump() for stage in open_solver_stages],
                        "message": "Open solver inicializado",
                    }
                ),
            )
    if execution_logger:
        await execution_logger.log_event(
            execution_id,
            execution_agent_id=planner_agent_id,
            event_type="planner_result",
            message=f"Plano gerado com {len(plan_output.steps)} passo(s)",
            raw_payload={
                "is_complex": plan_output.is_complex,
                "task_type": inferred_task_type,
                "steps": [step.model_dump() for step in plan_output.steps],
            },
        )
        await execution_logger.finish_agent(
            planner_agent_id,
            status="completed",
            output_payload={
                "is_complex": plan_output.is_complex,
                "step_count": len(plan_output.steps),
                "task_type": inferred_task_type,
            },
        )
    
    # ── Acknowledgment rápido (sempre, se disponível) ──
    if plan_output.acknowledgment:
        if plan_output.is_complex:
            # Planos complexos: acknowledgment como mensagem temporária de thinking
            # para não poluir os chunks do step terminal (ex: HTML do design_generator)
            yield sse("pre_action", plan_output.acknowledgment)
        else:
            yield sse("chunk", plan_output.acknowledgment)

    # ── Clarificação (se necessária, pausa o pipeline) ──
    if plan_output.needs_clarification and plan_output.questions:
        questions_payload = [q.model_dump() for q in plan_output.questions]
        yield sse("clarification", json.dumps(questions_payload))

        if execution_logger:
            await execution_logger.log_event(
                execution_id,
                event_type="clarification_requested",
                message=f"Aguardando clarificação do usuário ({len(plan_output.questions)} perguntas)",
                raw_payload={
                    "task_type": inferred_task_type,
                    "questions": questions_payload,
                    "acknowledgment": plan_output.acknowledgment,
                },
            )
            if mass_doc_stages:
                await _log_workflow_stages(
                    execution_logger,
                    execution_id,
                    workflow_id="mass_document_analysis",
                    stages=mass_doc_stages,
                    message="Pipeline documental aguardando objetivo do usuário",
                )
                yield sse(
                    "workflow_state",
                    json.dumps(
                        {
                            "workflow_id": "mass_document_analysis",
                            "stages": [stage.model_dump() for stage in mass_doc_stages],
                            "message": "Pipeline documental aguardando objetivo do usuário",
                        }
                    ),
                )
            if open_solver_stages:
                await _log_workflow_stages(
                    execution_logger,
                    execution_id,
                    workflow_id="open_problem_solving",
                    stages=open_solver_stages,
                    message="Open solver aguardando contexto do usuário",
                )
                yield sse(
                    "workflow_state",
                    json.dumps(
                        {
                            "workflow_id": "open_problem_solving",
                            "stages": [stage.model_dump() for stage in open_solver_stages],
                            "message": "Open solver aguardando contexto do usuário",
                        }
                    ),
                )
            await execution_logger.finish_execution(execution_id, status="awaiting_clarification")
        return

    if plan_output.is_complex and plan_output.steps:
        yield sse("steps", f"<step>Plano gerado: {len(plan_output.steps)} passos identificados.</step>")

        # ── Fallback de segurança: garantir que pelo menos o último step é terminal ──
        has_terminal = any(s.is_terminal for s in plan_output.steps)
        if not has_terminal:
            plan_output.steps[-1].is_terminal = True
            logger.info("[ORCHESTRATOR] Nenhum step marcado como terminal. Forçando último step como terminal.")
            if execution_logger:
                await execution_logger.log_event(
                    execution_id,
                    level="warning",
                    event_type="terminal_fallback",
                    message=f"Planner não marcou nenhum step como terminal. Último step ({plan_output.steps[-1].action}) forçado como terminal.",
                    raw_payload={"forced_step": plan_output.steps[-1].step, "forced_action": plan_output.steps[-1].action},
                )

        # O contexto acumulado que será passado de um agente para outro
        accumulated_context = ""
        final_answer = ""
        had_failures = False
        failure_summaries: list[str] = []
        abort_pipeline = False
        validation_trail: list[dict[str, Any]] = []
        capability_results: list[CapabilityResult] = []
        route_attempts: dict[str, int] = {}
        active_mass_doc_stages = (
            build_mass_document_stages(
                session_items=_get_session_inventory_items(session_id),
                awaiting_user_goal=False,
                delivery_completed=False,
            )
            if inferred_task_type == "mass_document_analysis"
            else None
        )

        # ── 2. Iteração do Plano ──
        for step in plan_output.steps:
            if abort_pipeline:
                break
            yield sse("steps", f"<step>Passo {step.step}/{len(plan_output.steps)}: {step.detail[:50]}...</step>")
            yield sse("thought", f"Iniciando ação '{step.action}': {step.detail}")
            if execution_logger:
                await execution_logger.log_event(
                    execution_id,
                    event_type="planner_step_started",
                    message=step.detail,
                    raw_payload={
                        **step.model_dump(),
                        "accumulated_context_chars": len(accumulated_context),
                    },
                )
                if active_mass_doc_stages:
                    stage_updates, stage_metadata = mass_document_updates_for_step_start(step.action)
                    if stage_updates or stage_metadata:
                        active_mass_doc_stages = update_workflow_stages(
                            active_mass_doc_stages,
                            status_by_stage=stage_updates,
                            metadata_by_stage=stage_metadata,
                        )
                        await _log_workflow_stages(
                            execution_logger,
                            execution_id,
                            workflow_id="mass_document_analysis",
                            stages=active_mass_doc_stages,
                            message=f"Pipeline documental avançou no step {step.step}",
                        )
                        yield sse(
                            "workflow_state",
                            json.dumps(
                                {
                                    "workflow_id": "mass_document_analysis",
                                    "stages": [stage.model_dump() for stage in active_mass_doc_stages],
                                    "message": f"Pipeline documental avançou no step {step.step}",
                                }
                            ),
                        )
            
            # Constrói temporariamente as mensagens injetando o contexto do passo anterior
            step_messages = [{"role": "system", "content": supervisor_prompt}]
            if session_inventory_message:
                step_messages.append({"role": "system", "content": session_inventory_message})
            step_messages += messages
            
            # Adiciona o contexto prévio ao LLM no momento da chamada da ferramenta
            execution_prompt = f"Seu objetivo atual: {step.detail}\n"
            if accumulated_context:
                execution_prompt += f"\nContexto prévio de passos anteriores (USE ESTES DADOS):\n{accumulated_context}"
            if inferred_task_type == "open_problem_solving" and open_solver_context:
                execution_prompt += "\n\n" + build_open_solver_prompt(
                    step_detail=step.detail,
                    scratchpad=open_solver_context,
                )
            step_handoff = None
            if step.action == "python" and inferred_task_type == "spreadsheet_generation":
                step_handoff = build_search_to_spreadsheet_handoff(context_results=capability_results)
                if step_handoff:
                    handoff_payload = step_handoff.model_dump()
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            event_type="step_handoff_prepared",
                            message=step_handoff.summary,
                            raw_payload=handoff_payload,
                        )
                    execution_prompt += (
                        "\n\nHANDOFF ESTRUTURADO PARA ESTE PASSO "
                        "(preserve estes itens como referência principal e não substitua nomes silenciosamente):\n"
                        + json.dumps(handoff_payload, ensure_ascii=False)
                    )
            
            step_messages.append({"role": "user", "content": execution_prompt})
            
            # Mapa de ação do Planner → nome da ferramenta do Supervisor.
            # Isso garante que o Supervisor chame a ferramenta certa para cada passo,
            # evitando que o LLM substitua ask_browser por ask_web_search, por exemplo.
            _forced_tool_name = planner_action_to_tool_name(step.action)
            _tool_choice = (
                {"type": "function", "function": {"name": _forced_tool_name}}
                if _forced_tool_name
                else "auto"
            )

            if step.action == "direct_answer":
                try:
                    final_result = await _generate_consolidated_response(
                        supervisor_prompt=supervisor_prompt,
                        supervisor_model=supervisor_model,
                        session_inventory_message=session_inventory_message or "",
                        user_intent=user_intent,
                        accumulated_context=accumulated_context,
                        had_failures=had_failures,
                        failure_summaries=failure_summaries,
                    )
                except Exception as exc:
                    logger.error("[ORCHESTRATOR] Erro ao gerar resposta direta do plano: %s", exc)
                    final_result = _sanitize_user_facing_response(
                        accumulated_context or "Desculpe, não consegui concluir a resposta com segurança.",
                        had_failures=True,
                    )
                async for event in _yield_text_chunks(final_result):
                    yield event
                if execution_logger:
                    await execution_logger.log_event(
                        execution_id,
                        event_type="pipeline_terminated",
                        message=f"Pipeline encerrado no step {step.step}/{len(plan_output.steps)} (direct_answer).",
                        raw_payload={
                            "step": step.step,
                            "action": step.action,
                            "capability_id": getattr(step, "capability_id", None),
                        },
                    )
                return

            try:
                supervisor_agent_id = None
                if execution_logger:
                    supervisor_agent_id = await execution_logger.start_agent(
                        execution_id,
                        agent_key="chat",
                        agent_name="Arcco Supervisor Especialista",
                        model=supervisor_model,
                        role="supervisor",
                        route=step.action,
                        input_payload={
                            "step_detail": step.detail,
                            "forced_tool_name": _forced_tool_name,
                            "capability_id": getattr(step, "capability_id", None),
                        },
                    )
                message = await _call_supervisor_for_step(
                    step_messages=step_messages,
                    supervisor_model=supervisor_model,
                    tool_choice=_tool_choice,
                    tools=active_tools,
                    forced_tool_name=_forced_tool_name,
                )
                if execution_logger:
                    await execution_logger.log_event(
                        execution_id,
                        execution_agent_id=supervisor_agent_id,
                        event_type="supervisor_message",
                        message=(message.get("content") or "")[:2000],
                        raw_payload={"tool_calls": message.get("tool_calls", [])},
                    )
                    await execution_logger.finish_agent(
                        supervisor_agent_id,
                        status="completed",
                        output_payload={"tool_calls": message.get("tool_calls", [])},
                    )
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Erro no LLM (Passo {step.step}): {e}")
                if execution_logger:
                    await execution_logger.log_event(
                        execution_id,
                        level="error",
                        event_type="supervisor_error",
                        message=str(e),
                        raw_payload={"step": step.step, "detail": step.detail},
                    )
                yield sse("error", f"Erro ao processar o Passo {step.step}: {e}")
                return

            supervisor_reasoning = (message.get("content") or "").strip()
            if message.get("tool_calls"):
                if supervisor_reasoning:
                    yield sse("pre_action", supervisor_reasoning)
                else:
                    ack = _build_pre_action_ack(message["tool_calls"])
                    if ack:
                        yield sse("pre_action", ack)

            # Tratamento da resposta do Supervisor / Tool Call
            if message.get("tool_calls"):
                tool_failed = False
                for tool in message["tool_calls"]:
                    func_name = tool["function"]["name"]
                    try:
                        func_args = json.loads(tool["function"]["arguments"])
                    except json.JSONDecodeError:
                        yield sse("steps", "<step>Erro de argumentos sub-agente. Ignorando...</step>")
                        continue

                    resolved = resolve_runtime_target(func_name)
                    if not resolved:
                        continue
                    route = resolved["route"]
                    route_semantics = get_runtime_semantics(
                        tool_name=func_name,
                        route=route,
                        planner_terminal=step.is_terminal,
                    )

                    recent_context = [m for m in step_messages if m.get("role") in ["user", "assistant"]][-5:]
                    tool_agent_id = None
                    if execution_logger:
                        tool_agent_id = await execution_logger.start_agent(
                            execution_id,
                            agent_key=route,
                            agent_name=route,
                            model=registry.get_model(route) or supervisor_model,
                            role=str(route_semantics["agent_role"]),
                            route=route,
                            input_payload={
                                "func_name": func_name,
                                "func_args": func_args,
                                "step": step.step,
                                "capability_id": getattr(step, "capability_id", None),
                                "step_handoff": step_handoff.model_dump() if step_handoff else None,
                            },
                        )
                    
                    # ── try/except protege cada tool para que um erro não mate o pipeline ──
                    try:

                        if route_semantics["direct_dispatch"]:
                            specialist_result = None
                            dispatch_info = None
                            dispatch_result: CapabilityResult | None = None
                            attempted_routes_for_step = {route}
                            current_route = route
                            current_func_name = func_name
                            current_func_args = dict(func_args)
                            while True:
                                route_attempts[current_route] = route_attempts.get(current_route, 0) + 1
                                dispatch_info = None
                                dispatch_result = None
                                dispatch_args = dict(current_func_args)
                                if current_route == "session_file":
                                    resolved_file, session_file_error = _resolve_session_file_request(
                                        session_id=session_id,
                                        requested_file_name=current_func_args.get("file_name"),
                                    )
                                    if session_file_error:
                                        specialist_result = session_file_error
                                        dispatch_info = {
                                            "tool_name": current_func_name,
                                            "message": "Leitura de arquivo da sessão bloqueada por inventário inválido",
                                            "error": True,
                                        }
                                        dispatch_result = CapabilityResult(
                                            capability_id=getattr(step, "capability_id", None) or current_route,
                                            route=current_route,
                                            status="failed",
                                            output_type="session_file_result",
                                            content=session_file_error,
                                            error_text=session_file_error,
                                            metadata={"message": dispatch_info["message"], "tool_name": current_func_name},
                                        )
                                        break
                                    if resolved_file:
                                        dispatch_args["file_name"] = (
                                            resolved_file.get("original_name")
                                            or resolved_file.get("file_name")
                                            or current_func_args.get("file_name")
                                            or ""
                                        )
                                if current_route == "deep_research":
                                    dispatch_args["_model"] = registry.get_model("deep_research") or supervisor_model
                                    dispatch_args["context"] = accumulated_context
                                elif current_route == "dynamic_skill":
                                    dispatch_args["_func_name"] = current_func_name
                                async for event in dispatch_direct_route(
                                    route=current_route,
                                    func_args=dispatch_args,
                                    user_id=user_id,
                                    mode="planner",
                                    step_label=f"Passo {step.step}",
                                    execute_tool_fn=execute_tool,
                                    exec_with_heartbeat_fn=_exec_with_heartbeat,
                                    exec_browser_with_progress_fn=_exec_browser_with_progress,
                                    emit_file_artifacts_fn=_emit_file_artifacts,
                                    browser_handoff_payload_fn=_browser_handoff_payload,
                                    is_error_result_fn=_is_error_result,
                                    sse_fn=sse,
                                    logger=logger,
                                    search_timeout=_SEARCH_TIMEOUT,
                                    browser_timeout=_BROWSER_TIMEOUT,
                                    skill_timeout=_SKILL_TIMEOUT,
                                ):
                                    if isinstance(event, dict) and "_dispatch" in event:
                                        dispatch_info = event["_dispatch"]
                                        if dispatch_info.get("result"):
                                            dispatch_result = CapabilityResult.model_validate(dispatch_info["result"])
                                            specialist_result = dispatch_result.content
                                        else:
                                            specialist_result = dispatch_info.get("specialist_result")
                                    else:
                                        yield event
                                if dispatch_info is None:
                                    specialist_result = specialist_result or f"Erro: route {current_route} não retornou resultado."
                                    dispatch_info = {
                                        "tool_name": current_func_name,
                                        "message": f"Execução concluída: {current_route}",
                                        "error": _is_error_result(specialist_result),
                                    }
                                if dispatch_result is None:
                                    dispatch_result = CapabilityResult(
                                        capability_id=getattr(step, "capability_id", None) or current_route,
                                        route=current_route,
                                        status="failed" if dispatch_info.get("error") else "completed",
                                        output_type="text",
                                        content=str(specialist_result or ""),
                                        handoff_required=bool(dispatch_info.get("handoff")),
                                        error_text=str(specialist_result or "") if dispatch_info.get("error") else None,
                                        metadata={"message": dispatch_info.get("message"), "tool_name": dispatch_info.get("tool_name")},
                                    )
                                if dispatch_info.get("error"):
                                    failure_decision = decide_on_route_failure(
                                        task_type=inferred_task_type,
                                        route=current_route,
                                        attempt_no=route_attempts[current_route],
                                        error_text=str(specialist_result or ""),
                                    )
                                    if execution_logger:
                                        await _log_policy_decision(
                                            execution_logger,
                                            execution_id,
                                            execution_agent_id=tool_agent_id,
                                            decision=failure_decision,
                                        )
                                    yield sse("policy_decision", json.dumps(failure_decision.model_dump()))
                                    if failure_decision.request_clarification and failure_decision.clarification_questions:
                                        async for clarification_event in _emit_policy_clarification(
                                            decision=failure_decision,
                                            execution_logger=execution_logger,
                                            execution_id=execution_id,
                                            execution_agent_id=tool_agent_id,
                                        ):
                                            yield clarification_event
                                        return
                                    if failure_decision.retry_same_route:
                                        yield sse("thought", f"{failure_decision.user_message} Tentando novamente {current_route}...")
                                        continue
                                    replan_decision = decide_route_replan(
                                        task_type=inferred_task_type,
                                        failed_route=current_route,
                                        func_args=current_func_args,
                                        step_detail=step.detail,
                                        user_intent=user_intent,
                                        attempted_routes=attempted_routes_for_step,
                                    )
                                    if replan_decision:
                                        attempted_routes_for_step.add(replan_decision.to_route)
                                        current_route = replan_decision.to_route
                                        current_func_name = replan_decision.to_tool_name
                                        current_func_args = build_replanned_args(
                                            task_type=inferred_task_type,
                                            failed_route=replan_decision.from_route,
                                            target_route=replan_decision.to_route,
                                            func_args=current_func_args,
                                            step_detail=step.detail,
                                            user_intent=user_intent,
                                        )
                                        if execution_logger:
                                            await _log_replan_decision(
                                                execution_logger,
                                                execution_id,
                                                execution_agent_id=tool_agent_id,
                                                decision=replan_decision,
                                            )
                                        yield sse("step_replanned", json.dumps(replan_decision.model_dump()))
                                        yield sse("thought", replan_decision.user_message)
                                        continue
                                break
                            if execution_logger:
                                await execution_logger.log_event(
                                    execution_id,
                                    execution_agent_id=tool_agent_id,
                                    level="warning" if dispatch_info.get("handoff") else "info",
                                    event_type="browser_handoff_requested" if dispatch_info.get("handoff") else "tool_result",
                                    message=dispatch_info.get("message"),
                                    tool_name=dispatch_info.get("tool_name"),
                                    tool_args=func_args,
                                    tool_result=dispatch_result.content[:2000] if dispatch_result.content else None,
                                    raw_payload={
                                        "dispatch_result": dispatch_result.model_dump(),
                                        "handoff_payload": dispatch_info.get("handoff_payload"),
                                    },
                                )
                            validation_result = validate_capability_execution(
                                task_type=inferred_task_type,
                                route=current_route,
                                capability_result=dispatch_result,
                                input_payload=current_func_args,
                                context_results=capability_results,
                                user_intent=user_intent,
                            )
                            if validation_result:
                                validation_payload = validation_result.model_dump()
                                validation_trail.append(validation_payload)
                                accumulated_context = _append_to_accumulated_context(
                                    accumulated_context,
                                    step=step.step,
                                    route="validation",
                                    content=_validation_summary_for_context(validation_result),
                                )
                                if execution_logger:
                                    await execution_logger.log_event(
                                        execution_id,
                                        execution_agent_id=tool_agent_id,
                                        level="warning" if validation_result.status != "valid" else "info",
                                        event_type="validation_result",
                                        message=validation_result.summary,
                                        raw_payload=validation_payload,
                                    )
                                validation_decision = decide_on_validation(
                                    task_type=inferred_task_type,
                                    route=current_route,
                                    validation_result=validation_result,
                                )
                                if execution_logger:
                                    await _log_policy_decision(
                                        execution_logger,
                                        execution_id,
                                        execution_agent_id=tool_agent_id,
                                        decision=validation_decision,
                                    )
                                yield sse("policy_decision", json.dumps(validation_decision.model_dump()))
                                if validation_decision.request_clarification and validation_decision.clarification_questions:
                                    async for clarification_event in _emit_policy_clarification(
                                        decision=validation_decision,
                                        execution_logger=execution_logger,
                                        execution_id=execution_id,
                                        execution_agent_id=tool_agent_id,
                                    ):
                                        yield clarification_event
                                    return
                                if validation_decision.metadata.get("suggested_replan_route"):
                                    replan_decision = decide_route_replan(
                                        task_type=inferred_task_type,
                                        failed_route=current_route,
                                        func_args=current_func_args,
                                        step_detail=step.detail,
                                        user_intent=user_intent,
                                        attempted_routes=attempted_routes_for_step,
                                    )
                                    if replan_decision:
                                        attempted_routes_for_step.add(replan_decision.to_route)
                                        current_route = replan_decision.to_route
                                        current_func_name = replan_decision.to_tool_name
                                        current_func_args = build_replanned_args(
                                            task_type=inferred_task_type,
                                            failed_route=replan_decision.from_route,
                                            target_route=replan_decision.to_route,
                                            func_args=current_func_args,
                                            step_detail=step.detail,
                                            user_intent=user_intent,
                                        )
                                        if execution_logger:
                                            await _log_replan_decision(
                                                execution_logger,
                                                execution_id,
                                                execution_agent_id=tool_agent_id,
                                                decision=replan_decision,
                                            )
                                        yield sse("step_replanned", json.dumps(replan_decision.model_dump()))
                                        yield sse("thought", replan_decision.user_message)
                                        continue
                            if dispatch_info.get("handoff"):
                                if execution_logger:
                                    await execution_logger.finish_agent(
                                        tool_agent_id,
                                        status="awaiting_clarification",
                                        output_payload={"preview": dispatch_info.get("message")},
                                        metadata={"resume_token": dispatch_info.get("resume_token")},
                                    )
                                    await execution_logger.finish_execution(execution_id, status="awaiting_clarification")
                                return
                            if _is_error_result(specialist_result):
                                had_failures = True
                                if inferred_task_type == "open_problem_solving" and open_solver_context:
                                    open_solver_context = update_open_solver_context(
                                        scratchpad=open_solver_context,
                                        route=current_route,
                                        success=False,
                                        result_preview=str(specialist_result or ""),
                                        artifacts=[],
                                    )
                                    if execution_logger:
                                        await execution_logger.log_event(
                                            execution_id,
                                            execution_agent_id=tool_agent_id,
                                            event_type="open_solver_scratchpad_updated",
                                            message=f"Scratchpad atualizado com falha em {current_route}",
                                            raw_payload=open_solver_context,
                                        )
                                failure_decision = decide_on_route_failure(
                                    task_type=inferred_task_type,
                                    route=current_route,
                                    attempt_no=route_attempts.get(current_route, 1),
                                    error_text=str(specialist_result or ""),
                                )
                                tool_failed = bool(failure_decision.should_abort and not failure_decision.continue_partial)
                                if execution_logger and active_mass_doc_stages:
                                    stage_updates, stage_metadata = mass_document_updates_for_step_result(route, success=False)
                                    if stage_updates or stage_metadata:
                                        active_mass_doc_stages = update_workflow_stages(
                                            active_mass_doc_stages,
                                            status_by_stage=stage_updates,
                                            metadata_by_stage=stage_metadata,
                                        )
                                        await _log_workflow_stages(
                                            execution_logger,
                                            execution_id,
                                            workflow_id="mass_document_analysis",
                                            stages=active_mass_doc_stages,
                                            message=f"Pipeline documental registrou falha em {route}",
                                        )
                                        yield sse(
                                            "workflow_state",
                                            json.dumps(
                                                {
                                                    "workflow_id": "mass_document_analysis",
                                                    "stages": [stage.model_dump() for stage in active_mass_doc_stages],
                                                    "message": f"Pipeline documental registrou falha em {route}",
                                                }
                                            ),
                                        )
                                if current_route == "session_file":
                                    failure_msg = f"Falha ao consultar o anexo {func_args.get('file_name', '') or 'da sessão'}."
                                elif current_route == "web_search":
                                    failure_msg = f"Falha na pesquisa web para '{func_args.get('query', '')[:80]}'."
                                elif current_route == "python":
                                    failure_msg = "Falha na execução Python deste passo."
                                elif current_route == "deep_research":
                                    failure_msg = f"Falha na pesquisa profunda para '{func_args.get('query', '')[:80]}'."
                                elif current_route == "dynamic_skill":
                                    failure_msg = f"Falha na skill {current_func_name}: {specialist_result}"
                                else:
                                    failure_msg = f"Falha ao acessar {func_args.get('url', '')} no navegador."
                                failure_summaries.append(failure_msg)
                                accumulated_context = _append_to_accumulated_context(
                                    accumulated_context,
                                    step=step.step,
                                    route=route,
                                    content=specialist_result,
                                    error=True,
                                )
                                if execution_logger:
                                    await _log_policy_decision(
                                        execution_logger,
                                        execution_id,
                                        execution_agent_id=tool_agent_id,
                                        decision=failure_decision,
                                    )
                                    if failure_decision.request_clarification and failure_decision.clarification_questions:
                                        await execution_logger.log_event(
                                            execution_id,
                                            execution_agent_id=tool_agent_id,
                                            event_type="clarification_suggested",
                                            message=failure_decision.user_message,
                                            raw_payload={"questions": [q.model_dump() for q in failure_decision.clarification_questions]},
                                        )
                                yield sse("policy_decision", json.dumps(failure_decision.model_dump()))
                                yield sse("thought", failure_decision.user_message or failure_msg)
                            else:
                                capability_results.append(dispatch_result)
                                if inferred_task_type == "open_problem_solving" and open_solver_context:
                                    open_solver_context = update_open_solver_context(
                                        scratchpad=open_solver_context,
                                        route=current_route,
                                        success=True,
                                        result_preview=str(specialist_result or ""),
                                        artifacts=[artifact.model_dump() for artifact in dispatch_result.artifacts],
                                    )
                                    if execution_logger:
                                        await execution_logger.log_event(
                                            execution_id,
                                            execution_agent_id=tool_agent_id,
                                            event_type="open_solver_scratchpad_updated",
                                            message=f"Scratchpad atualizado após {current_route}",
                                            raw_payload=open_solver_context,
                                        )
                                        open_solver_stages = build_open_solver_stages(
                                            awaiting_user_goal=False,
                                            delivery_completed=bool(step.is_terminal),
                                            steps_used=int(open_solver_context.get("steps_used") or 0),
                                            step_budget=int(open_solver_context.get("step_budget") or 0),
                                        )
                                        await _log_workflow_stages(
                                            execution_logger,
                                            execution_id,
                                            workflow_id="open_problem_solving",
                                            stages=open_solver_stages,
                                            message=f"Open solver avançou com {current_route}",
                                        )
                                        yield sse(
                                            "workflow_state",
                                            json.dumps(
                                                {
                                                    "workflow_id": "open_problem_solving",
                                                    "stages": [stage.model_dump() for stage in open_solver_stages],
                                                    "message": f"Open solver avançou com {current_route}",
                                                }
                                            ),
                                        )
                                if execution_logger and active_mass_doc_stages:
                                    stage_updates, stage_metadata = mass_document_updates_for_step_result(current_route, success=True)
                                    if stage_updates or stage_metadata:
                                        active_mass_doc_stages = update_workflow_stages(
                                            active_mass_doc_stages,
                                            status_by_stage=stage_updates,
                                            metadata_by_stage=stage_metadata,
                                        )
                                        await _log_workflow_stages(
                                            execution_logger,
                                            execution_id,
                                            workflow_id="mass_document_analysis",
                                            stages=active_mass_doc_stages,
                                            message=f"Pipeline documental concluiu {route}",
                                        )
                                        yield sse(
                                            "workflow_state",
                                            json.dumps(
                                                {
                                                    "workflow_id": "mass_document_analysis",
                                                    "stages": [stage.model_dump() for stage in active_mass_doc_stages],
                                                    "message": f"Pipeline documental concluiu {route}",
                                                }
                                            ),
                                        )
                                accumulated_context = _append_to_accumulated_context(
                                    accumulated_context,
                                    step=step.step,
                                    route=current_route,
                                    content=specialist_result,
                                )
                                if current_route == "session_file":
                                    yield sse("thought", f"Arquivo de sessão consultado: {func_args.get('file_name', '')}")
                                elif current_route == "web_search":
                                    yield sse("thought", f"Dados obtidos da web via busca: {func_args.get('query', '')}")
                                elif current_route == "python":
                                    yield sse("thought", f"Resultado do código Python: {str(specialist_result)[:120]}...")
                                elif current_route == "deep_research":
                                    yield sse("thought", f"Pesquisa profunda concluída para: {func_args.get('query', '')[:120]}")
                                elif current_route == "dynamic_skill":
                                    yield sse("thought", f"Skill {current_func_name} executada com sucesso.")
                                    if step.is_terminal and route_semantics["artifact_terminal"]:
                                        local_rendered_design = _render_local_design_if_possible(str(specialist_result))
                                        if local_rendered_design:
                                            if execution_logger:
                                                await execution_logger.log_event(
                                                    execution_id,
                                                    execution_agent_id=tool_agent_id,
                                                    event_type="terminal_result",
                                                    message=f"Resultado terminal gerado por {func_name}",
                                                    raw_payload={
                                                        "preview": local_rendered_design[:2000],
                                                        "is_terminal": True,
                                                        "artifact_only": True,
                                                        "forced_terminal": True,
                                                    },
                                                )
                                                await execution_logger.finish_agent(
                                                    tool_agent_id,
                                                    status="completed",
                                                    output_payload={
                                                        "preview": local_rendered_design[:2000],
                                                        "artifact_only": True,
                                                        "forced_terminal": True,
                                                    },
                                                )
                                            remaining_steps = [s.step for s in plan_output.steps if s.step > step.step]
                                            if execution_logger:
                                                await execution_logger.log_event(
                                                    execution_id,
                                                    event_type="pipeline_terminated",
                                                    message=f"Pipeline encerrado no step {step.step}/{len(plan_output.steps)} ({func_name}, terminal artifact).",
                                                    raw_payload={
                                                        "artifact_only": True,
                                                        "skipped_steps": remaining_steps,
                                                        "terminal_step": step.step,
                                                        "terminal_route": func_name,
                                                        "accumulated_context_chars": len(accumulated_context),
                                                    },
                                                )
                                            async for artifact_event in _emit_design_artifact(local_rendered_design):
                                                yield artifact_event
                                            return
                                else:
                                    yield sse("thought", f"Extração de {func_args.get('url', '')} concluída com sucesso. Analisando dados...")

                        elif route == "spy_pages":
                            yield sse("steps", f"<step>Analisando sites via SimilarWeb (Passo {step.step})...</step>")
                            spy_result = await execute_tool("analyze_web_pages", func_args, user_id=user_id)
                            # Emite evento especial para o frontend renderizar o card
                            yield f'data: {json.dumps({"type": "spy_pages_result", "data": spy_result})}\n\n'
                            accumulated_context = _append_to_accumulated_context(
                                accumulated_context,
                                step=step.step,
                                route="spy_pages",
                                content=spy_result,
                            )
                            yield sse("thought", "Dados SimilarWeb obtidos com sucesso.")


                        elif route_semantics["terminal_specialist"]:
                            # Ferramentas que PODEM ser terminais (text_generator, design_generator)
                            # O planner decide via step.is_terminal se este step encerra o pipeline
                            local_rendered_design = None
                            if route == "text_generator":
                                content = f"Título sugerido: {func_args.get('title_hint', '')}\nContexto Prévio: {accumulated_context}\nInstruções: {func_args.get('instructions', '')}"
                            elif route == "design_generator" and route_semantics["supports_local_design_render"]:
                                design_context = _extract_visual_context_for_design(accumulated_context)
                                local_rendered_design = _render_local_design_if_possible(design_context)
                                content = f"Contexto Prévio:\n{design_context}\n\nInstruções: {func_args.get('instructions', '')}"
                            else:
                                content = json.dumps(func_args)

                            temp_msgs = recent_context + [{"role": "user", "content": content}]
                            route_prompt = registry.get_prompt(route)
                            route_model = registry.get_model(route) or supervisor_model
                            route_tools = registry.get_tools(route)

                            if local_rendered_design:
                                final_result = local_rendered_design
                            else:
                                final_result = await _run_terminal_one_shot(
                                    temp_msgs,
                                    route_model,
                                    route_prompt,
                                    route_tools,
                                    user_id=user_id,
                                )
                            terminal_result = _build_specialist_capability_result(
                                route=route,
                                content=str(final_result),
                                error=_is_error_result(final_result),
                                metadata={
                                    "step": step.step,
                                    "is_terminal": step.is_terminal,
                                    "preview_kind": "terminal_specialist",
                                },
                            )
                            if execution_logger:
                                await execution_logger.log_event(
                                    execution_id,
                                    execution_agent_id=tool_agent_id,
                                    event_type="terminal_result" if step.is_terminal else "intermediate_result",
                                    message=f"Resultado {'terminal' if step.is_terminal else 'intermediário'} gerado por {route}",
                                    raw_payload=terminal_result.model_dump(),
                                )

                            if _is_error_result(final_result):
                                had_failures = True
                                tool_failed = True
                                failure_msg = f"Falha na etapa terminal {route}."
                                failure_summaries.append(failure_msg)
                                accumulated_context = _append_to_accumulated_context(
                                    accumulated_context,
                                    step=step.step,
                                    route=route,
                                    content=final_result,
                                    error=True,
                                )
                                yield sse("thought", failure_msg)
                            elif step.is_terminal:
                                # ── TERMINAL: envia direto ao frontend e para o pipeline ──
                                if route == "text_generator":
                                    doc_match = _DOC_TAG_RE.search(final_result)
                                    if doc_match:
                                        doc_title = doc_match.group(1).strip()
                                        doc_content = doc_match.group(2).strip()
                                        yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                                        final_result = _DOC_TAG_RE.sub(doc_content, final_result)
                                elif route == "design_generator":
                                    design_html = _extract_design_html(final_result)
                                    if design_html:
                                        async for artifact_event in _emit_design_artifact(design_html):
                                            yield artifact_event
                                        if execution_logger:
                                            await execution_logger.finish_agent(
                                                tool_agent_id,
                                                status="completed",
                                                output_payload={"preview": design_html[:2000], "artifact_only": True, "capability_result": terminal_result.model_dump()},
                                            )
                                        remaining_steps = [s.step for s in plan_output.steps if s.step > step.step]
                                        if execution_logger:
                                            await execution_logger.log_event(
                                                execution_id,
                                                event_type="pipeline_terminated",
                                                message=f"Pipeline encerrado no step {step.step}/{len(plan_output.steps)} ({route}, terminal artifact).",
                                                raw_payload={
                                                    "terminal_step": step.step,
                                                    "terminal_route": route,
                                                    "skipped_steps": remaining_steps,
                                                    "accumulated_context_chars": len(accumulated_context),
                                                    "artifact_only": True,
                                                },
                                            )
                                        return

                                chunk_size = 40
                                for i in range(0, len(final_result), chunk_size):
                                    yield sse("chunk", final_result[i:i + chunk_size])
                                if execution_logger:
                                    await execution_logger.finish_agent(
                                        tool_agent_id,
                                        status="completed",
                                        output_payload={"preview": final_result[:2000], "capability_result": terminal_result.model_dump()},
                                    )

                                # Já enviou pro usuário, termina por aqui
                                remaining_steps = [s.step for s in plan_output.steps if s.step > step.step]
                                if execution_logger:
                                    await execution_logger.log_event(
                                        execution_id,
                                        event_type="pipeline_terminated",
                                        message=f"Pipeline encerrado no step {step.step}/{len(plan_output.steps)} ({route}, terminal).",
                                        raw_payload={
                                            "terminal_step": step.step,
                                            "terminal_route": route,
                                            "skipped_steps": remaining_steps,
                                            "accumulated_context_chars": len(accumulated_context),
                                        },
                                    )
                                return
                            else:
                                # ── NÃO-TERMINAL: acumula resultado e continua pro próximo step ──
                                if route == "text_generator":
                                    doc_match = _DOC_TAG_RE.search(final_result)
                                    if doc_match:
                                        yield sse("text_doc", json.dumps({
                                            "title": doc_match.group(1).strip(),
                                            "content": doc_match.group(2).strip(),
                                        }))

                                accumulated_context = _append_to_accumulated_context(
                                    accumulated_context,
                                    step=step.step,
                                    route=route,
                                    content=final_result,
                                )
                                yield sse("thought", f"Passo {step.step} ({route}) concluído. Resultado acumulado para o próximo passo.")
                                if execution_logger:
                                    await execution_logger.finish_agent(
                                        tool_agent_id,
                                        status="completed",
                                        output_payload={"preview": final_result[:2000], "capability_result": terminal_result.model_dump()},
                                    )
                                    await execution_logger.log_event(
                                        execution_id,
                                        event_type="context_accumulated",
                                        message=f"Step {step.step} ({route}) acumulou resultado. Contexto total: {len(accumulated_context)} chars.",
                                        raw_payload={
                                            "step": step.step,
                                            "route": route,
                                            "result_chars": len(final_result),
                                            "accumulated_context_chars": len(accumulated_context),
                                            "capability_result": terminal_result.model_dump(),
                                        },
                                    )
                        else:
                            # File Modifier (Não-Terminal)
                            file_url = func_args.get("file_url")
                            session_ref = ""
                            if func_args.get("session_id") and func_args.get("file_name"):
                                session_ref = (
                                    f"Sessão: {func_args.get('session_id')} "
                                    f"Arquivo da sessão: {func_args.get('file_name')}\n"
                                )
                            content = (
                                f"Contexto: {accumulated_context}\n"
                                f"Arquivo remoto: {file_url or 'N/A'}\n"
                                f"{session_ref}"
                                f"Instruções: {func_args.get('instructions')}"
                            )
                            temp_msgs = recent_context + [{"role": "user", "content": content}]
                            specialist_result = ""
                            async for event in _run_guarded_specialist(
                                route,
                                user_intent,
                                temp_msgs,
                                supervisor_model,
                                f"Modificando arquivo (Passo {step.step})...",
                                user_id=user_id,
                            ):
                                if event.startswith("RESULT:"):
                                    specialist_result = event[7:]
                                else:
                                    yield event
                            if execution_logger:
                                specialist_contract = _build_specialist_capability_result(
                                    route=route,
                                    content=specialist_result,
                                    error=_is_error_result(specialist_result),
                                    metadata={"step": step.step, "preview_kind": "guarded_specialist"},
                                )
                                await execution_logger.log_event(
                                    execution_id,
                                    execution_agent_id=tool_agent_id,
                                    event_type="specialist_result",
                                    message=f"Especialista {route} concluído",
                                    raw_payload=specialist_contract.model_dump(),
                                )
                            async for artifact_event in _emit_file_artifacts(specialist_result):
                                yield artifact_event

                            # ANTI-LEAK
                            if route_requires_link_only(route):
                                md_links = _extract_storage_markdown_links(specialist_result)
                                if md_links:
                                    links_only = "\n".join(f"[{label}]({url})" for label, url in md_links)
                                    specialist_result = f"Arquivo gerado.\n\n{links_only}"

                            accumulated_context = _append_to_accumulated_context(
                                accumulated_context,
                                step=step.step,
                                route="file_modifier",
                                content=specialist_result,
                            )
                            if execution_logger:
                                await execution_logger.finish_agent(
                                    tool_agent_id,
                                    status="completed",
                                    output_payload={"preview": specialist_result[:2000], "capability_result": specialist_contract.model_dump()},
                                )

                        if execution_logger and route in DIRECT_DISPATCH_ROUTES:
                            success_preview = locals().get("specialist_result") or locals().get("research_result") or ""
                            await execution_logger.finish_agent(
                                tool_agent_id,
                                status="failed" if _is_error_result(success_preview) else "completed",
                                output_payload={"preview": str(success_preview)[:2000]},
                                error_text=str(success_preview)[:2000] if _is_error_result(success_preview) else None,
                            )

                    except Exception as tool_exc:
                        # Captura qualquer erro (ImportError, timeout, etc.) sem matar o pipeline
                        logger.error(f"[ORCHESTRATOR] Erro na tool '%s' (Passo %s): %s", func_name, step.step, tool_exc)
                        error_msg = f"Ferramenta '{func_name}' falhou: {tool_exc}"
                        had_failures = True
                        tool_failed = True
                        failure_summaries.append(error_msg)
                        accumulated_context = _append_to_accumulated_context(
                            accumulated_context,
                            step=step.step,
                            route=route,
                            content=error_msg,
                            error=True,
                        )
                        yield sse("thought", f"Erro no passo {step.step}: {error_msg}")
                        if execution_logger:
                            await execution_logger.log_event(
                                execution_id,
                                execution_agent_id=tool_agent_id,
                                level="error",
                                event_type="tool_error",
                                message=error_msg,
                                tool_name=func_name,
                                tool_args=func_args,
                            )
                            await execution_logger.finish_agent(
                                tool_agent_id,
                                status="failed",
                                error_text=error_msg,
                            )

                if tool_failed:
                    abort_pipeline = True
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            level="warning",
                            event_type="pipeline_aborted",
                            message=f"Pipeline interrompido após falha no passo {step.step}.",
                            raw_payload={"step": step.step, "failures": failure_summaries[-3:]},
                        )
                    break

            else:
                # O LLM decidiu não usar TOOL, apenas gerou texto
                fallback_content = message.get("content", "")
                if _forced_tool_name:
                    error_msg = (
                        f"Falha crítica: o modelo não emitiu a tool obrigatória '{_forced_tool_name}'. "
                        f"Resposta recebida: {fallback_content[:160]}"
                    )
                    logger.error(
                        "[ORCHESTRATOR] Passo %s exigia tool '%s', mas o supervisor respondeu sem tool_call. Conteúdo: %s",
                        step.step,
                        _forced_tool_name,
                        fallback_content[:300],
                    )
                    yield sse("thought", f"Erro crítico no passo {step.step}: o modelo falhou ao acionar a ferramenta obrigatória.")
                    yield sse("error", "Houve uma falha interna de roteamento da IA. O processo foi interrompido para evitar erro em cascata.")
                    had_failures = True
                    failure_summaries.append(error_msg)
                    accumulated_context = _append_to_accumulated_context(
                        accumulated_context,
                        step=step.step,
                        route=_forced_tool_name,
                        content=error_msg,
                        error=True,
                    )
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            level="error",
                            event_type="pipeline_aborted",
                            message=error_msg,
                            raw_payload={
                                "step": step.step,
                                "expected_tool": _forced_tool_name,
                                "supervisor_response": fallback_content[:500],
                                "failure_class": "tool_contract_violation",
                            },
                        )
                        await execution_logger.finish_execution(
                            execution_id,
                            status="failed",
                            final_error=error_msg,
                        )
                    abort_pipeline = True
                    break
                else:
                    accumulated_context = _append_to_accumulated_context(
                        accumulated_context,
                        step=step.step,
                        route="raciocínio",
                        content=fallback_content,
                    )
                
        # Fim do loop do Planner
        # Agora geramos a resposta final conversacional consolidando o accumulated_context
        yield sse("steps", "<step>Consolidando resultados dos passos...</step>")
        yield sse("thought", "Organizando os resultados coletados e redigindo a resposta final...")
        
        try:
            final_response = await _generate_consolidated_response(
                supervisor_prompt=supervisor_prompt,
                supervisor_model=supervisor_model,
                session_inventory_message=session_inventory_message or "",
                user_intent=user_intent,
                accumulated_context=accumulated_context,
                had_failures=had_failures,
                failure_summaries=failure_summaries,
            )
            async for event in _yield_text_chunks(final_response):
                yield event
            if execution_logger:
                await execution_logger.log_event(
                    execution_id,
                    event_type="final_response_generated",
                    message="Resposta final consolidada enviada ao usuário",
                )
                await execution_logger.log_event(
                    execution_id,
                    event_type="execution_trace_summary",
                    message="Resumo de task type, validação e trilha do pipeline",
                    raw_payload={
                        "task_type": inferred_task_type,
                        "execution_engine": execution_engine,
                        "preconditions": precondition_check.model_dump(),
                        "task_type_definition": task_type_definition,
                        "validation_trail": validation_trail,
                        "capability_results_count": len(capability_results),
                        "quality_summary": {
                            "had_failures": had_failures,
                            "failure_count": len(failure_summaries),
                            "validation_count": len(validation_trail),
                            "ended_with_clarification": False,
                        },
                    },
                )
                if inferred_task_type == "mass_document_analysis":
                    await _log_workflow_stages(
                        execution_logger,
                        execution_id,
                        workflow_id="mass_document_analysis",
                        stages=build_mass_document_stages(
                            session_items=_get_session_inventory_items(session_id),
                            awaiting_user_goal=False,
                            delivery_completed=True,
                        ),
                        message="Pipeline documental concluído",
                    )
                    yield sse(
                        "workflow_state",
                        json.dumps(
                            {
                                "workflow_id": "mass_document_analysis",
                                "stages": [
                                    stage.model_dump()
                                    for stage in build_mass_document_stages(
                                        session_items=_get_session_inventory_items(session_id),
                                        awaiting_user_goal=False,
                                        delivery_completed=True,
                                    )
                                ],
                                "message": "Pipeline documental concluído",
                            }
                        ),
                    )
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Erro no streaming final consolidado: %s", exc)
            if execution_logger:
                await execution_logger.log_event(
                    execution_id,
                    level="error",
                    event_type="final_response_error",
                    message=str(exc),
                )
            yield sse("error", f"Falha ao consolidar a resposta final: {exc}")
            fallback_text = _sanitize_user_facing_response(
                accumulated_context or "Desculpe, não consegui consolidar a resposta final.",
                had_failures=True,
            )
            async for event in _yield_text_chunks(fallback_text):
                yield event

        return

    # ── 3. Fallback / Sem Planejamento Complexo (Execução Normal ReAct) ──
    yield sse("thought", "Pedido direto. Respondendo ou acionando a ferramenta aplicável.")
    direct_task_type = infer_task_type(user_intent)
    direct_task_type_definition = get_task_type_definition(direct_task_type) or {}
    direct_validation_trail: list[dict[str, Any]] = []
    direct_capability_results: list[CapabilityResult] = []
    direct_route_attempts: dict[str, int] = {}
    direct_mass_doc_stages = (
        build_mass_document_stages(
            session_items=_get_session_inventory_items(session_id),
            awaiting_user_goal=False,
            delivery_completed=False,
        )
        if direct_task_type == "mass_document_analysis"
        else None
    )
    if execution_logger:
        await execution_logger.log_event(
            execution_id,
            event_type="direct_mode_started",
            message="Fluxo ReAct sem plano complexo iniciado",
            raw_payload={
                "task_type": direct_task_type,
                "task_type_definition": direct_task_type_definition,
            },
        )
        if direct_mass_doc_stages:
            await _log_workflow_stages(
                execution_logger,
                execution_id,
                workflow_id="mass_document_analysis",
                stages=direct_mass_doc_stages,
                message="Pipeline documental iniciado em modo direto",
            )
            yield sse(
                "workflow_state",
                json.dumps(
                    {
                        "workflow_id": "mass_document_analysis",
                        "stages": [stage.model_dump() for stage in direct_mass_doc_stages],
                        "message": "Pipeline documental iniciado em modo direto",
                    }
                ),
            )
    current_messages = [{"role": "system", "content": supervisor_prompt}]
    if session_inventory_message:
        current_messages.append({"role": "system", "content": session_inventory_message})
    current_messages += messages
    referenced_session_file = _select_referenced_session_file(user_intent, session_id)
    MAX_ITERATIONS = 3

    for iteration in range(MAX_ITERATIONS):
        if iteration == 0:
            yield sse("steps", "<step>Analisando pedido e planejando execução...</step>")

        # Chama o LLM do Supervisor
        try:
            data = await _call_openrouter_with_timeout(
                timeout=_SUPERVISOR_TIMEOUT,
                label=f"Supervisor ({supervisor_model})",
                messages=current_messages,
                model=supervisor_model,
                max_tokens=4096,
                tools=active_tools,
            )
            message = data["choices"][0]["message"]
        except (KeyError, IndexError) as e:
            logger.error(f"[ORCHESTRATOR] Resposta LLM malformada: {e}")
            yield sse("error", "Erro interno ao processar a resposta da IA. Tente novamente.")
            return
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Erro na chamada LLM: {e}")
            yield sse("error", f"Erro ao comunicar com a IA: {e}")
            return

        current_messages.append(message)

        # Pre-action Acknowledgement — texto do modelo ou fallback contextual
        # Emitido como "pre_action" para o frontend exibir no bubble do assistente
        supervisor_reasoning = (message.get("content") or "").strip()
        if message.get("tool_calls"):
            if supervisor_reasoning:
                yield sse("pre_action", supervisor_reasoning)
            else:
                ack = _build_pre_action_ack(message["tool_calls"])
                if ack:
                    yield sse("pre_action", ack)

        # ── O Supervisor decidiu usar uma Ferramenta? ────────────────────
        if message.get("tool_calls"):
            for tool in message["tool_calls"]:
                func_name = tool["function"]["name"]

                try:
                    func_args = json.loads(tool["function"]["arguments"])
                except json.JSONDecodeError:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": "Erro sintático no JSON da ferramenta. Corrija a formatação e tente novamente.",
                    })
                    yield sse("steps", "<step>Aguardando sub-agente corrigir os parâmetros da ferramenta...</step>")
                    continue

                resolved = resolve_runtime_target(func_name)
                if not resolved:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": f"Erro: ferramenta '{func_name}' não suportada pelo orquestrador.",
                    })
                    continue
                route = resolved["route"]
                route_semantics = get_runtime_semantics(tool_name=func_name, route=route)
                react_agent_id = None
                if execution_logger:
                    react_agent_id = await execution_logger.start_agent(
                        execution_id,
                        agent_key=route,
                        agent_name=route,
                        model=registry.get_model(route) or model,
                        role=str(route_semantics["agent_role"]),
                        route=route,
                        input_payload={"func_name": func_name, "func_args": func_args, "iteration": iteration},
                    )

                # Contexto recente para sub-agentes
                recent_context = [m for m in messages if m.get("role") in ["user", "assistant"]][-5:]

                if route == "browser" and referenced_session_file:
                    route = "session_file"
                    func_name = "read_session_file"
                    func_args = {
                        "session_id": session_id,
                        "file_name": (
                            referenced_session_file.get("original_name")
                            or referenced_session_file.get("file_name")
                            or ""
                        ),
                    }
                    route_semantics = get_runtime_semantics(tool_name=func_name, route=route)

                # ── ROTA: Pesquisa Web Rápida (direto, sem sub-agente extra) ──
                if route_semantics["direct_dispatch"]:
                    specialist_result = None
                    dispatch_info = None
                    dispatch_result: CapabilityResult | None = None
                    attempted_routes_for_turn = {route}
                    current_route = route
                    current_func_name = func_name
                    current_func_args = dict(func_args)
                    if execution_logger and direct_mass_doc_stages:
                        stage_updates, stage_metadata = mass_document_updates_for_step_start(current_route)
                        if stage_updates or stage_metadata:
                            direct_mass_doc_stages = update_workflow_stages(
                                direct_mass_doc_stages,
                                status_by_stage=stage_updates,
                                metadata_by_stage=stage_metadata,
                            )
                            await _log_workflow_stages(
                                execution_logger,
                                execution_id,
                                workflow_id="mass_document_analysis",
                                stages=direct_mass_doc_stages,
                                message=f"Pipeline documental avançou em {route}",
                            )
                            yield sse(
                                "workflow_state",
                                json.dumps(
                                    {
                                        "workflow_id": "mass_document_analysis",
                                        "stages": [stage.model_dump() for stage in direct_mass_doc_stages],
                                        "message": f"Pipeline documental avançou em {route}",
                                    }
                                ),
                            )
                    while True:
                        direct_route_attempts[current_route] = direct_route_attempts.get(current_route, 0) + 1
                        dispatch_info = None
                        dispatch_result = None
                        dispatch_args = dict(current_func_args)
                        if current_route == "session_file":
                            resolved_file, session_file_error = _resolve_session_file_request(
                                session_id=session_id,
                                requested_file_name=current_func_args.get("file_name"),
                            )
                            if session_file_error:
                                specialist_result = session_file_error
                                dispatch_info = {
                                    "tool_name": current_func_name,
                                    "message": "Leitura de arquivo da sessão bloqueada por inventário inválido",
                                    "error": True,
                                }
                                dispatch_result = CapabilityResult(
                                    capability_id=current_route,
                                    route=current_route,
                                    status="failed",
                                    output_type="session_file_result",
                                    content=session_file_error,
                                    error_text=session_file_error,
                                    metadata={"message": dispatch_info["message"], "tool_name": current_func_name},
                                )
                                break
                            if resolved_file:
                                dispatch_args["file_name"] = (
                                    resolved_file.get("original_name")
                                    or resolved_file.get("file_name")
                                    or current_func_args.get("file_name")
                                    or ""
                                )
                        if current_route == "deep_research":
                            dispatch_args["_model"] = registry.get_model("deep_research") or supervisor_model
                        elif current_route == "dynamic_skill":
                            dispatch_args["_func_name"] = current_func_name
                        async for event in dispatch_direct_route(
                            route=current_route,
                            func_args=dispatch_args,
                            user_id=user_id,
                            mode="react",
                            step_label=f"Iteração {iteration}",
                            execute_tool_fn=execute_tool,
                            exec_with_heartbeat_fn=_exec_with_heartbeat,
                            exec_browser_with_progress_fn=_exec_browser_with_progress,
                            emit_file_artifacts_fn=_emit_file_artifacts,
                            browser_handoff_payload_fn=_browser_handoff_payload,
                            is_error_result_fn=_is_error_result,
                            sse_fn=sse,
                            logger=logger,
                            search_timeout=_SEARCH_TIMEOUT,
                            browser_timeout=_BROWSER_TIMEOUT,
                            skill_timeout=_SKILL_TIMEOUT,
                        ):
                            if isinstance(event, dict) and "_dispatch" in event:
                                dispatch_info = event["_dispatch"]
                                if dispatch_info.get("result"):
                                    dispatch_result = CapabilityResult.model_validate(dispatch_info["result"])
                                    specialist_result = dispatch_result.content
                                else:
                                    specialist_result = dispatch_info.get("specialist_result")
                            else:
                                yield event
                        if dispatch_info is None:
                            specialist_result = specialist_result or f"Erro: route {current_route} não retornou resultado."
                            dispatch_info = {
                                "tool_name": current_func_name,
                                "message": f"Execução concluída: {current_route}",
                                "error": _is_error_result(specialist_result),
                            }
                        if dispatch_result is None:
                            dispatch_result = CapabilityResult(
                                capability_id=current_route,
                                route=current_route,
                                status="failed" if dispatch_info.get("error") else "completed",
                                output_type="text",
                                content=str(specialist_result or ""),
                                handoff_required=bool(dispatch_info.get("handoff")),
                                error_text=str(specialist_result or "") if dispatch_info.get("error") else None,
                                metadata={"message": dispatch_info.get("message"), "tool_name": dispatch_info.get("tool_name")},
                            )
                        if dispatch_info.get("error"):
                            failure_decision = decide_on_route_failure(
                                task_type=direct_task_type,
                                route=current_route,
                                attempt_no=direct_route_attempts[current_route],
                                error_text=str(specialist_result or ""),
                            )
                            if execution_logger:
                                await _log_policy_decision(
                                    execution_logger,
                                    execution_id,
                                    execution_agent_id=react_agent_id,
                                    decision=failure_decision,
                                )
                            yield sse("policy_decision", json.dumps(failure_decision.model_dump()))
                            if failure_decision.retry_same_route:
                                yield sse("thought", f"{failure_decision.user_message} Tentando novamente {current_route}...")
                                continue
                            if failure_decision.request_clarification and failure_decision.clarification_questions:
                                async for clarification_event in _emit_policy_clarification(
                                    decision=failure_decision,
                                    execution_logger=execution_logger,
                                    execution_id=execution_id,
                                    execution_agent_id=react_agent_id,
                                ):
                                    yield clarification_event
                                return
                            replan_decision = decide_route_replan(
                                task_type=direct_task_type,
                                failed_route=current_route,
                                func_args=current_func_args,
                                step_detail=user_intent,
                                user_intent=user_intent,
                                attempted_routes=attempted_routes_for_turn,
                            )
                            if replan_decision:
                                attempted_routes_for_turn.add(replan_decision.to_route)
                                current_route = replan_decision.to_route
                                current_func_name = replan_decision.to_tool_name
                                current_func_args = build_replanned_args(
                                    task_type=direct_task_type,
                                    failed_route=replan_decision.from_route,
                                    target_route=replan_decision.to_route,
                                    func_args=current_func_args,
                                    step_detail=user_intent,
                                    user_intent=user_intent,
                                )
                                if execution_logger:
                                    await _log_replan_decision(
                                        execution_logger,
                                        execution_id,
                                        execution_agent_id=react_agent_id,
                                        decision=replan_decision,
                                    )
                                yield sse("step_replanned", json.dumps(replan_decision.model_dump()))
                                yield sse("thought", replan_decision.user_message)
                                continue
                        break
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            execution_agent_id=react_agent_id,
                            level="warning" if dispatch_info.get("handoff") else "info",
                            event_type="browser_handoff_requested" if dispatch_info.get("handoff") else "tool_result",
                            message=dispatch_info.get("message"),
                            tool_name=dispatch_info.get("tool_name"),
                            tool_args=current_func_args,
                            tool_result=dispatch_result.content[:2000] if dispatch_result.content else None,
                            raw_payload={
                                "dispatch_result": dispatch_result.model_dump(),
                                "handoff_payload": dispatch_info.get("handoff_payload"),
                            },
                        )
                    validation_result = validate_capability_execution(
                        task_type=direct_task_type,
                        route=current_route,
                        capability_result=dispatch_result,
                        input_payload=current_func_args,
                        context_results=direct_capability_results,
                        user_intent=user_intent,
                    )
                    if validation_result:
                        validation_decision = decide_on_validation(
                            task_type=direct_task_type,
                            route=current_route,
                            validation_result=validation_result,
                        )
                        direct_validation_trail.append(validation_result.model_dump())
                        if execution_logger:
                            await execution_logger.log_event(
                                execution_id,
                                execution_agent_id=react_agent_id,
                                level="warning" if validation_result.status != "valid" else "info",
                                event_type="validation_result",
                                message=validation_result.summary,
                                raw_payload=validation_result.model_dump(),
                            )
                            await _log_policy_decision(
                                execution_logger,
                                execution_id,
                                execution_agent_id=react_agent_id,
                                decision=validation_decision,
                            )
                        yield sse("policy_decision", json.dumps(validation_decision.model_dump()))
                        if validation_decision.request_clarification and validation_decision.clarification_questions:
                            async for clarification_event in _emit_policy_clarification(
                                decision=validation_decision,
                                execution_logger=execution_logger,
                                execution_id=execution_id,
                                execution_agent_id=react_agent_id,
                            ):
                                yield clarification_event
                            return
                        if validation_decision.metadata.get("suggested_replan_route"):
                            replan_decision = decide_route_replan(
                                task_type=direct_task_type,
                                failed_route=current_route,
                                func_args=current_func_args,
                                step_detail=func_args.get("instructions") or user_intent,
                                user_intent=user_intent,
                                attempted_routes=attempted_routes_for_turn,
                            )
                            if replan_decision:
                                attempted_routes_for_turn.add(replan_decision.to_route)
                                current_route = replan_decision.to_route
                                current_func_name = replan_decision.to_tool_name
                                current_func_args = build_replanned_args(
                                    task_type=direct_task_type,
                                    failed_route=replan_decision.from_route,
                                    target_route=replan_decision.to_route,
                                    func_args=current_func_args,
                                    step_detail=func_args.get("instructions") or user_intent,
                                    user_intent=user_intent,
                                )
                                if execution_logger:
                                    await _log_replan_decision(
                                        execution_logger,
                                        execution_id,
                                        execution_agent_id=react_agent_id,
                                        decision=replan_decision,
                                    )
                                yield sse("step_replanned", json.dumps(replan_decision.model_dump()))
                                yield sse("thought", replan_decision.user_message)
                                continue
                    if dispatch_info.get("handoff"):
                        if execution_logger:
                            await execution_logger.finish_agent(
                                react_agent_id,
                                status="awaiting_clarification",
                                output_payload={"preview": dispatch_info.get("message")},
                                metadata={"resume_token": dispatch_info.get("resume_token")},
                            )
                            await execution_logger.finish_execution(execution_id, status="awaiting_clarification")
                        return
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    direct_capability_results.append(dispatch_result)
                    if execution_logger and direct_mass_doc_stages:
                        stage_updates, stage_metadata = mass_document_updates_for_step_result(
                            current_route,
                            success=not _is_error_result(specialist_result),
                        )
                        if stage_updates or stage_metadata:
                            direct_mass_doc_stages = update_workflow_stages(
                                direct_mass_doc_stages,
                                status_by_stage=stage_updates,
                                metadata_by_stage=stage_metadata,
                            )
                            await _log_workflow_stages(
                                execution_logger,
                                execution_id,
                                workflow_id="mass_document_analysis",
                                stages=direct_mass_doc_stages,
                                message=f"Pipeline documental atualizou {route}",
                            )
                            yield sse(
                                "workflow_state",
                                json.dumps(
                                    {
                                        "workflow_id": "mass_document_analysis",
                                        "stages": [stage.model_dump() for stage in direct_mass_doc_stages],
                                        "message": f"Pipeline documental atualizou {route}",
                                    }
                                ),
                            )
                    if current_route == "session_file":
                        yield sse("steps", "<step>Leitura do anexo concluída — integrando contexto...</step>")
                    elif current_route == "web_search":
                        if dispatch_info.get("error"):
                            current_messages.append({
                                "role": "system",
                                "content": (
                                    "A busca web falhou. NÃO invente dados nem cite resultados não verificados. "
                                    "Explique a limitação ao usuário e peça outra abordagem se necessário."
                                ),
                            })
                        else:
                            current_messages.append({
                                "role": "system",
                                "content": (
                                    "Os dados da busca foram obtidos com sucesso. "
                                    "Sintetize as informações recebidas e responda ao usuário agora de forma clara e objetiva. "
                                    "NÃO chame mais ferramentas de busca."
                                ),
                            })
                        yield sse("steps", "<step>Dados recebidos — elaborando resposta...</step>")
                    elif route == "python":
                        yield sse("steps", "<step>Código executado — integrando resultado...</step>")
                    elif route == "browser":
                        if dispatch_info.get("error"):
                            yield sse("browser_action", json.dumps({
                                "status": "error",
                                "url": func_args.get("url", ""),
                                "title": str(specialist_result)[:100],
                            }))
                            current_messages.append({
                                "role": "system",
                                "content": (
                                    "O navegador falhou ou está indisponível. "
                                    "NÃO tente usar ask_browser novamente. "
                                    "NÃO invente dados da página nem diga que conseguiu acessar algo que falhou. "
                                    "Aguarde a rota de recuperação definida pelo harness ou responda apenas com as informações realmente disponíveis. "
                                    "Caso contrário, responda ao usuário com as informações disponíveis."
                                ),
                            })
                        else:
                            yield sse("browser_action", json.dumps({
                                "status": "done",
                                "url": func_args.get("url", ""),
                                "title": "Página lida com sucesso",
                            }))
                        yield sse("steps", "<step>Conteúdo extraído — analisando dados...</step>")
                    elif route == "deep_research":
                        if dispatch_info.get("error"):
                            current_messages.append({
                                "role": "system",
                                "content": (
                                    "A pesquisa profunda falhou ou foi inconclusiva. "
                                    "NÃO invente fatos nem cite fontes não verificadas. "
                                    "Explique a limitação ao usuário."
                                ),
                            })
                        yield sse("steps", "<step>Pesquisa profunda concluída — preparando resposta...</step>")
                    elif route == "dynamic_skill":
                        if dispatch_info.get("error"):
                            current_messages.append({
                                "role": "system",
                                "content": (
                                    f"A skill {func_name} falhou. NÃO invente a saída dessa skill. "
                                    "Explique a limitação ou siga com os dados já disponíveis."
                                ),
                            })
                            yield sse("thought", f"Falha na skill {func_name}.")
                        else:
                            yield sse("thought", f"Skill {func_name} executada com sucesso.")
                            if route_semantics["artifact_terminal"]:
                                local_rendered = _render_local_design_if_possible(str(specialist_result))
                                if local_rendered:
                                    if execution_logger:
                                        await execution_logger.log_event(
                                            execution_id,
                                            execution_agent_id=react_agent_id,
                                            event_type="terminal_result",
                                            message="Resultado visual convertido em terminal por static_design_generator",
                                            raw_payload={"preview": local_rendered[:2000], "artifact_only": True, "forced_terminal": True},
                                        )
                                        await execution_logger.finish_agent(
                                            react_agent_id,
                                            status="completed",
                                            output_payload={"preview": local_rendered[:2000], "artifact_only": True, "forced_terminal": True},
                                        )
                                        await _log_pipeline_terminated(
                                            execution_logger,
                                            execution_id,
                                            route="static_design_generator",
                                            artifact_only=True,
                                        )
                                    async for artifact_event in _emit_design_artifact(local_rendered):
                                        yield artifact_event
                                    return
                    if execution_logger:
                        await execution_logger.finish_agent(
                            react_agent_id,
                            status="failed" if dispatch_info.get("error") else "completed",
                            output_payload={"preview": str(specialist_result)[:2000]},
                            error_text=str(specialist_result) if dispatch_info.get("error") else None,
                        )
                    if route == "session_file" and dispatch_info.get("error"):
                        yield sse("error", specialist_result)
                        return
                    if route == "python" and dispatch_info.get("error"):
                        yield sse("error", specialist_result)
                        return

                # ── ROTA: Spy Pages (SimilarWeb via Apify) ──
                elif route == "spy_pages":
                    urls = func_args.get("urls", [])
                    yield sse("steps", f"<step>Analisando {len(urls)} site(s) via SimilarWeb...</step>")
                    spy_result = await execute_tool("analyze_web_pages", func_args, user_id=user_id)
                    # Emite evento especial para o frontend renderizar o card
                    yield f'data: {json.dumps({"type": "spy_pages_result", "data": spy_result})}\n\n'
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            execution_agent_id=react_agent_id,
                            event_type="tool_result",
                            message=f"Análise SimilarWeb concluída para {len(urls)} site(s)",
                            tool_name="analyze_web_pages",
                            tool_args=func_args,
                            tool_result=spy_result[:2000],
                        )
                        await execution_logger.finish_agent(
                            react_agent_id,
                            status="completed",
                            output_payload={"preview": spy_result[:500]},
                        )
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": spy_result,
                    })
                    current_messages.append({
                        "role": "system",
                        "content": (
                            "Os dados do SimilarWeb foram obtidos com sucesso e exibidos ao usuário como card interativo. "
                            "Faça um breve resumo dos dados encontrados e pergunte como o usuário quer prosseguir."
                        ),
                    })
                    yield sse("steps", "<step>Dados SimilarWeb recebidos — preparando resposta...</step>")


                # ── ROTA: Terminal (text_generator, design_generator) ──
                elif route_semantics["terminal_specialist"]:
                    local_rendered_design = None
                    if route == "text_generator":
                        step_message = "Estruturando documento bruto e preparando preview..."
                        content = (
                            f"Título sugerido: {func_args.get('title_hint', '')}\n"
                            f"Instruções: {func_args.get('instructions', '')}\n"
                            f"Contexto: {func_args.get('content_brief', '')}"
                        )
                    elif route == "design_generator" and route_semantics["supports_local_design_render"]:
                        step_message = "Construindo design editável e preparando preview..."
                        message_context = _extract_template_payload_from_messages(recent_context) or _extract_template_payload_from_any_messages(current_messages)
                        local_rendered_design = _render_local_design_if_possible(message_context)
                        guided_context = ""
                        if message_context:
                            try:
                                from backend.services.design_template_renderer import parse_template_payload
                                parsed_payload = parse_template_payload(message_context) or {}
                                if parsed_payload:
                                    guided_context = (
                                        "\nCONTRATO VISUAL ESTRUTURADO:\n"
                                        f"{json.dumps(parsed_payload, ensure_ascii=False)}\n"
                                    )
                            except Exception:
                                logger.exception("[ORCHESTRATOR] Falha ao anexar contrato visual ao design_generator.")
                        content = (
                            f"Título sugerido: {func_args.get('title_hint', '')}\n"
                            "Instruções: Gere por padrão uma peça quadrada 1:1, alinhada, centralizada, "
                            "contida em um único canvas e pronta para preview/exportação. "
                            "Só fuja do formato quadrado se o usuário pedir explicitamente outro formato. "
                            f"{func_args.get('instructions', '')}\n"
                            f"Contexto: {func_args.get('content_brief', '')}\n"
                            f"Direção visual: {func_args.get('design_direction', '')}"
                            f"{guided_context}"
                        )
                    else:
                        step_message = "Processando..."
                        content = json.dumps(func_args)

                    temp_msgs = recent_context + [{"role": "user", "content": content}]

                    yield sse("steps", f"<step>{step_message}</step>")
                    route_prompt = registry.get_prompt(route)
                    route_model = registry.get_model(route) or model
                    route_tools = registry.get_tools(route)

                    if local_rendered_design:
                        final_result = local_rendered_design
                    else:
                        final_result = await _run_terminal_one_shot(
                            temp_msgs,
                            route_model,
                            route_prompt,
                            route_tools,
                            user_id=user_id,
                        )
                    terminal_result = _build_specialist_capability_result(
                        route=route,
                        content=str(final_result),
                        error=_is_error_result(final_result),
                        metadata={"iteration": iteration, "preview_kind": "terminal_specialist"},
                    )
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            execution_agent_id=react_agent_id,
                            event_type="terminal_result",
                            message=f"Resultado terminal gerado por {route}",
                            raw_payload=terminal_result.model_dump(),
                        )

                    if route == "text_generator":
                        doc_match = _DOC_TAG_RE.search(final_result)
                        if doc_match:
                            doc_title = doc_match.group(1).strip()
                            doc_content = doc_match.group(2).strip()
                            yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                            final_result = _DOC_TAG_RE.sub(doc_content, final_result)
                    elif route == "design_generator":
                        design_html = _extract_design_html(final_result)
                        if design_html:
                            async for artifact_event in _emit_design_artifact(design_html):
                                yield artifact_event
                            if execution_logger:
                                await execution_logger.finish_agent(
                                    react_agent_id,
                                    status="completed",
                                    output_payload={"preview": design_html[:2000], "artifact_only": True, "capability_result": terminal_result.model_dump()},
                                )
                                await _log_pipeline_terminated(
                                    execution_logger,
                                    execution_id,
                                    route=route,
                                    artifact_only=True,
                                )
                            return

                    chunk_size = 40
                    for i in range(0, len(final_result), chunk_size):
                        yield sse("chunk", final_result[i:i + chunk_size])
                    if execution_logger:
                        await execution_logger.finish_agent(
                            react_agent_id,
                            status="completed",
                            output_payload={"preview": final_result[:2000], "capability_result": terminal_result.model_dump()},
                        )
                        if direct_mass_doc_stages and direct_task_type == "mass_document_analysis":
                            await _log_workflow_stages(
                                execution_logger,
                                execution_id,
                                workflow_id="mass_document_analysis",
                                stages=build_mass_document_stages(
                                    session_items=_get_session_inventory_items(session_id),
                                    awaiting_user_goal=False,
                                    delivery_completed=True,
                                ),
                                message="Pipeline documental concluído em modo direto",
                            )
                        await _log_pipeline_terminated(
                            execution_logger,
                            execution_id,
                            route=route,
                        )

                    # Proteção do frontend: encerra o loop do Supervisor
                    return

                # ── ROTA: Não-terminal com guardrails (file_modifier) ──
                else:
                    if route == "file_modifier":
                        step_message = "Lendo estrutura do arquivo original e aplicando modificações..."
                        file_url = func_args.get("file_url")
                        session_ref = ""
                        if func_args.get("session_id") and func_args.get("file_name"):
                            session_ref = (
                                f"Sessão: {func_args.get('session_id')} "
                                f"Arquivo da sessão: {func_args.get('file_name')} "
                            )
                        content = (
                            f"Arquivo: {file_url or 'N/A'} "
                            f"{session_ref}"
                            f"Instruções: {func_args.get('instructions')}"
                        )
                    else:
                        step_message = "Processando com especialista..."
                        content = json.dumps(func_args)

                    temp_msgs = recent_context + [{"role": "user", "content": content}]

                    specialist_result = ""
                    async for event in _run_guarded_specialist(
                        route,
                        user_intent,
                        temp_msgs,
                        model,
                        step_message,
                        user_id=user_id,
                    ):
                        if event.startswith("RESULT:"):
                            specialist_result = event[7:]
                        else:
                            yield event

                    if not specialist_result.strip():
                        specialist_result = "O especialista não retornou resultado. Tente reformular o pedido."
                        logger.warning(f"[ORCHESTRATOR] Especialista '{route}' retornou vazio")
                    specialist_contract = _build_specialist_capability_result(
                        route=route,
                        content=specialist_result,
                        error=_is_error_result(specialist_result),
                        metadata={"iteration": iteration, "preview_kind": "guarded_specialist"},
                    )

                    if route == "design_generator" and route_semantics["supports_local_design_render"]:
                        design_html = _extract_design_html(specialist_result)
                        if design_html:
                            if execution_logger:
                                await execution_logger.log_event(
                                    execution_id,
                                    execution_agent_id=react_agent_id,
                                    event_type="terminal_result",
                                    message="Resultado visual convertido em terminal por design_generator",
                                    raw_payload={
                                        **specialist_contract.model_dump(),
                                        "metadata": {
                                            **specialist_contract.metadata,
                                            "forced_terminal": True,
                                            "artifact_only": True,
                                        },
                                    },
                                )
                                await execution_logger.finish_agent(
                                    react_agent_id,
                                    status="completed",
                                    output_payload={"preview": design_html[:2000], "forced_terminal": True, "artifact_only": True, "capability_result": specialist_contract.model_dump()},
                                )

                            async for artifact_event in _emit_design_artifact(design_html):
                                yield artifact_event
                            return

                    # ANTI-LEAK: Para rotas de arquivo, enviar APENAS o link pro Supervisor
                    if route_requires_link_only(route):
                        async for artifact_event in _emit_file_artifacts(specialist_result):
                            yield artifact_event
                        md_links = _extract_storage_markdown_links(specialist_result)
                        if md_links:
                            links_only = "\n".join(f"[{label}]({url})" for label, url in md_links)
                            specialist_result = f"Arquivo gerado com sucesso.\n\n{links_only}"
                            logger.info("[ANTI-LEAK] Conteúdo suprimido. Apenas link enviado ao Supervisor.")

                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tool["id"],
                        "content": specialist_result,
                    })
                    if execution_logger:
                        await execution_logger.log_event(
                            execution_id,
                            execution_agent_id=react_agent_id,
                            event_type="specialist_result",
                            message=f"Especialista {route} concluído",
                            raw_payload=specialist_contract.model_dump(),
                        )
                        await execution_logger.finish_agent(
                            react_agent_id,
                            status="completed",
                            output_payload={"preview": specialist_result[:2000], "capability_result": specialist_contract.model_dump()},
                        )

                    yield sse("steps", "<step>Integrando resultado do especialista...</step>")

            # Fim do loop de tool_calls, prossegue para o Supervisor responder
            continue

        else:
            # O Supervisor decidiu responder ao usuário diretamente
            yield sse("steps", "<step>Preparando resposta final...</step>")

            content = message.get("content", "")
            doc_match = _DOC_TAG_RE.search(content)
            if doc_match:
                doc_title = doc_match.group(1).strip()
                doc_content = doc_match.group(2).strip()
                yield sse("text_doc", json.dumps({"title": doc_title, "content": doc_content}))
                cleaned_content = _DOC_TAG_RE.sub(doc_content, content)
                if cleaned_content:
                    yield sse("chunk", cleaned_content)
                return

            # A resposta já está em message["content"] — fazemos streaming direto sem segunda chamada LLM.
            final_content = _sanitize_user_facing_response(
                content or "Desculpe, não consegui gerar uma resposta. Tente novamente."
            )
            async for event in _yield_text_chunks(final_content):
                yield event
            if execution_logger and direct_mass_doc_stages and direct_task_type == "mass_document_analysis":
                await _log_workflow_stages(
                    execution_logger,
                    execution_id,
                    workflow_id="mass_document_analysis",
                    stages=build_mass_document_stages(
                        session_items=_get_session_inventory_items(session_id),
                        awaiting_user_goal=False,
                        delivery_completed=True,
                    ),
                    message="Pipeline documental concluído em resposta direta",
                )

            return

    # Se saiu do loop, atingiu MAX_ITERATIONS
    yield sse("error", "Limite máximo de processamento atingido. Por favor, seja mais específico na sua solicitação.")
