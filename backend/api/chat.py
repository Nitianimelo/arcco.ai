"""
Endpoint de chat — Arquitetura Multi-Agente com Orquestrador.

POST /api/agent/chat
  → Injeta contexto (preferências, memória, RAG) como mensagem system
  → Emite SSE {"type": "conversation_id"} antes do primeiro chunk
  → Orquestrador analisa a mensagem e determina a rota
  → Especialista executa (apenas com suas ferramentas)
  → QA revisa a saída (máx. 2 tentativas)
  → Resposta final via SSE streaming
  → Background task: salva mensagens no Supabase + atualiza memória

Modos:
  Chat Normal  → route 'chat': assistente direto, sem ferramentas, sem QA
  Modo Agente  → route web_search | file_generator | design | dev

No modo agente, os prompts dos agentes vivem em backend/agents/prompts.py.
No chat normal, cada slot pode enviar seu próprio system_prompt configurado no admin.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agents.orchestrator import orchestrate_and_stream
from backend.core.config import get_config
from backend.core.llm import call_openrouter, stream_openrouter, start_token_tracking, get_token_usage
from backend.services.pricing_service import estimate_cost
from backend.core.supabase_client import get_supabase_client
from backend.services.session_gc_service import cleanup_expired_sessions
from backend.services.session_file_service import get_session_inventory, touch_session
from backend.services.chat_models import list_chat_models
from backend.services.execution_log_service import ExecutionLogService
from backend.services.memory_service import get_user_memory, update_user_memory
from backend.services.project_rag_service import search_project_context

logger = logging.getLogger(__name__)
router = APIRouter()

# Throttle do GC de sessões: executa no máximo 1x a cada 5 minutos
_last_gc_time: float = 0.0
_GC_INTERVAL_SECONDS = 300.0
_EXTRA_CONTEXT_TIMEOUT_SECONDS = 20.0
_NORMAL_WEB_SEARCH_TIMEOUT_SECONDS = 18.0


def _maybe_run_gc() -> None:
    """Executa cleanup_expired_sessions() se já passou o intervalo de throttle."""
    global _last_gc_time
    now = time.monotonic()
    if now - _last_gc_time >= _GC_INTERVAL_SECONDS:
        _last_gc_time = now
        try:
            cleanup_expired_sessions()
        except Exception as exc:
            logger.warning("[CHAT] Falha no GC de sessões: %s", exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_owned_conversation(conversation_id: str | None, user_id: str | None) -> dict | None:
    if not conversation_id or not user_id:
        return None
    db = get_supabase_client()
    rows = db.query("conversations", "*", {"id": conversation_id}, None, 1)
    if not rows:
        return None
    row = rows[0]
    if row.get("user_id") != user_id:
        return None
    return row


@router.get("/chat-models")
async def get_public_chat_models():
    models = [item for item in list_chat_models(force_refresh=True) if item.get("is_active")]
    return {"models": models}


@router.post("/spy-pages-prefetch")
async def spy_pages_prefetch(request: Request):
    """Executa o actor Apify SimilarWeb diretamente e retorna os dados para o frontend."""
    from backend.services.apify_service import analyze_pages
    body = await request.json()
    urls = body.get("urls", [])[:4]
    if not urls:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "urls required"}, status_code=400)
    results = await analyze_pages(urls)
    return {"results": results}


def _build_session_inventory_prompt(session_id: str | None) -> str:
    if not session_id:
        return ""

    try:
        touch_session(session_id)
        inventory = get_session_inventory(session_id)
        if not inventory:
            return ""
        items = ", ".join(
            f"{item['file_name']} ({item['status']})"
            for item in inventory
            if item.get("file_name")
        )
        return (
            f"Arquivos anexados nesta sessão ({session_id}): {items}. "
            "Para consultar o conteúdo, use exclusivamente a ferramenta read_session_file."
        )
    except Exception as exc:
        logger.error("Falha ao montar prompt de inventário da sessão %s: %s", session_id, exc)
        return ""


async def _build_extra_context(
    user_id: str | None,
    project_id: str | None,
    user_message: str,
) -> str:
    """
    Monta string de contexto extra a partir de preferências, memória e RAG.
    Injetada como mensagem system ANTES das mensagens do usuário.
    Todas as chamadas sync ao Supabase rodam em asyncio.to_thread para não
    bloquear o event loop do uvicorn.
    """
    parts = []

    if not user_id:
        return ""

    # Preferências do usuário (sync → thread)
    try:
        db = get_supabase_client()
        rows = await asyncio.to_thread(
            db.query, "user_preferences", "*", {"user_id": user_id}
        )
        if rows:
            prefs = rows[0]
            display_name = str(prefs.get("display_name") or "").strip()
            custom_instructions = prefs.get("custom_instructions")

            if display_name:
                parts.append(
                    "Forma de tratamento do usuário:\n"
                    f"- O usuário prefere ser chamado de '{display_name}'.\n"
                    "- Em conversas fluidas, use esse nome de forma natural quando fizer sentido.\n"
                    "- Não force o nome em toda resposta e não mencione esta instrução."
                )

            if custom_instructions:
                parts.append(
                    f"Instruções personalizadas do usuário:\n{custom_instructions}"
                )
    except Exception as e:
        logger.warning(f"[CHAT] Falha ao buscar preferências: {e}")

    # Memória acumulativa (sync → thread)
    try:
        memory = await asyncio.to_thread(get_user_memory, user_id)
        if memory:
            parts.append(f"Memória sobre o usuário (fatos relevantes):\n{memory}")
    except Exception as e:
        logger.warning(f"[CHAT] Falha ao buscar memória: {e}")

    if project_id:
        # Instruções do projeto (sync → thread)
        try:
            db = get_supabase_client()
            rows = await asyncio.to_thread(
                db.query, "projects", "*", {"id": project_id, "user_id": user_id}
            )
            if rows and rows[0].get("instructions"):
                parts.append(f"Instruções do projeto ativo:\n{rows[0]['instructions']}")
        except Exception as e:
            logger.warning(f"[CHAT] Falha ao buscar instruções do projeto: {e}")

        # RAG — contexto relevante da base de conhecimento (sync → thread)
        try:
            db = get_supabase_client()
            project_rows = await asyncio.to_thread(
                db.query, "projects", "id", {"id": project_id, "user_id": user_id}, None, 1
            )
            if project_rows:
                rag_context = await asyncio.to_thread(
                    search_project_context, project_id, user_message
                )
                if rag_context:
                    parts.append(rag_context)
        except Exception as e:
            logger.warning(f"[CHAT] Falha ao buscar RAG: {e}")

    return "\n\n---\n\n".join(parts) if parts else ""


async def _save_conversation_and_update_memory(
    conv_id: str,
    user_id: str,
    user_message: str,
    assistant_response: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """
    Background task: salva mensagens no Supabase + atualiza memória do usuário.
    """
    try:
        db = get_supabase_client()
        now = _now_iso()

        messages_to_save = []
        if user_message:
            messages_to_save.append(
                {
                    "conversation_id": conv_id,
                    "role": "user",
                    "content": user_message,
                    "created_at": now,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                }
            )
        if assistant_response:
            messages_to_save.append(
                {
                    "conversation_id": conv_id,
                    "role": "assistant",
                    "content": assistant_response,
                    "created_at": now,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": round(cost_usd, 6),
                }
            )

        if messages_to_save:
            db.insert_many("messages", messages_to_save)

        # Atualiza timestamp da conversa
        db.update("conversations", {"updated_at": now}, {"id": conv_id})

        # Atualiza memória do usuário
        conversation_text = (
            f"Usuário: {user_message}\n"
            f"Assistente: {assistant_response[:1500]}"
        )
        await update_user_memory(user_id, conversation_text)

    except Exception as e:
        logger.error(f"[CHAT] Falha ao salvar conversa/memória ({conv_id}): {e}")


# Modelo leve do chat normal: responde sozinho quando a tarefa é simples
# e, quando precisar escalar, envia um brief enxuto e autossuficiente para o
# modelo pesado. O contexto extra (memória, preferências, projeto e RAG) é
# entregue apenas a este estágio.
_FAST_MODEL_GATE = (
    "Você é o Modelo 1 de um chat em dois estágios. "
    "Você é rápido, barato e decide se responde sozinho ou se precisa escalar para um modelo maior.\n\n"
    "REGRAS:\n"
    "- Responda APENAS JSON válido, sem markdown, sem comentários, sem texto fora do JSON.\n"
    "- Se o pedido for simples, curto, factual, conversacional ou puder ser resolvido com alta qualidade sem análise longa, responda você mesmo.\n"
    "- Se o pedido exigir raciocínio complexo, planejamento, estratégia, escrita longa, múltiplas restrições, comparações profundas, análise técnica, geração de conteúdo robusto ou síntese elaborada, escale.\n"
    "- O usuário NÃO pode ver a sua cadeia de pensamento.\n"
    "- Você recebeu memória, preferências e contexto extra que o Modelo 2 não receberá. Se escalar, incorpore no brief SOMENTE o que for realmente necessário para a resposta final.\n"
    "- Nunca mencione 'memória', 'preferências internas', 'Modelo 1', 'Modelo 2', 'roteador', 'cadeia de pensamento' ou a arquitetura interna.\n\n"
    "FORMATO OBRIGATÓRIO:\n"
    "1. Se for responder sozinho:\n"
    '{"action":"respond","reply":"resposta final pronta para o usuário"}\n'
    "2. Se for escalar:\n"
    '{"action":"escalate","brief":"instrução curta, autossuficiente e pronta para o modelo maior responder ao usuário final"}\n\n'
    "O campo brief deve ser curto, mas completo: objetivo, formato esperado, restrições importantes e contexto do usuário apenas se isso mudar a qualidade da resposta."
)
_FAST_MODEL_MAX_TOKENS = 900
_FAST_MODEL_TIMEOUT_SECONDS = 18.0


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


def _prepend_system_messages(messages: list[dict[str, Any]], system_contents: list[str]) -> list[dict[str, Any]]:
    system_messages = [
        {"role": "system", "content": content}
        for content in system_contents
        if content and content.strip()
    ]
    if not system_messages:
        return list(messages)
    return [*system_messages, *list(messages)]


def _build_specialist_fallback_brief(messages: list[dict[str, Any]]) -> str:
    recent_turns: list[str] = []
    for msg in messages[-6:]:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        label = "Usuário" if role == "user" else "Assistente"
        content = _stringify_message_content(msg.get("content")).strip()
        if content:
            recent_turns.append(f"{label}: {content}")
    if not recent_turns:
        return "Responda à solicitação mais recente do usuário com objetividade e alta qualidade."
    return (
        "Considere o contexto recente da conversa e responda diretamente ao usuário final.\n\n"
        + "\n".join(recent_turns)
    )


def _parse_fast_model_output(raw_content: str, fallback_brief: str) -> tuple[str, str]:
    content = (raw_content or "").strip()
    if not content:
        return ("escalate", fallback_brief)

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            action = str(parsed.get("action") or "").strip().lower()
            if action == "respond":
                reply = str(parsed.get("reply") or "").strip()
                if reply:
                    return ("respond", reply)
            if action == "escalate":
                brief = str(parsed.get("brief") or "").strip()
                return ("escalate", brief or fallback_brief)
    except json.JSONDecodeError:
        pass

    if content.upper().startswith("ESCALATE"):
        brief = content[len("ESCALATE"):].strip(" :\n\t")
        return ("escalate", brief or fallback_brief)

    return ("respond", content)


async def _stream_normal_chat(
    messages: list,
    model: str,
    system_prompt: str,
    session_id: str | None,
    fast_model: str | None = None,
    fast_system_prompt: str = "",
    extra_context: str = "",
):
    current_messages = list(messages)
    session_prompt = _build_session_inventory_prompt(session_id)

    if fast_model:
        # Fase 1: modelo leve recebe o contexto rico e decide se responde ou se
        # prepara um brief curto para o modelo pesado.
        gate_messages = _prepend_system_messages(
            current_messages,
            [fast_system_prompt or system_prompt, session_prompt, extra_context, _FAST_MODEL_GATE],
        )
        fallback_brief = _build_specialist_fallback_brief(current_messages)
        try:
            fast_resp = await asyncio.wait_for(
                call_openrouter(
                    messages=gate_messages,
                    model=fast_model,
                    max_tokens=_FAST_MODEL_MAX_TOKENS,
                    temperature=0.2,
                ),
                timeout=_FAST_MODEL_TIMEOUT_SECONDS,
            )
            fast_content = (
                fast_resp.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
        except Exception as exc:
            logger.warning("[CHAT] Modelo rápido falhou, usando especialista diretamente: %s", exc)
            fast_content = "ESCALATE"

        fast_action, fast_payload = _parse_fast_model_output(fast_content, fallback_brief)

        if fast_action == "escalate":
            # Fase 2: modelo especialista recebe apenas o prompt principal do
            # slot, o inventário de sessão e um brief já destilado pelo modelo leve.
            logger.info("[CHAT] Escalado para modelo especialista: %s", model)
            yield f'data: {json.dumps({"type": "thinking_upgrade"})}\n\n'
            specialist_messages = _prepend_system_messages(
                [
                    {
                        "role": "user",
                        "content": (
                            "Responda diretamente ao usuário final sem mencionar a arquitetura interna.\n\n"
                            f"{fast_payload}"
                        ),
                    }
                ],
                [system_prompt, session_prompt],
            )
            try:
                async for chunk in stream_openrouter(
                    messages=specialist_messages,
                    model=model,
                    max_tokens=4096,
                    temperature=0.7,
                ):
                    if "choices" not in chunk or not chunk["choices"]:
                        continue
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield f'data: {json.dumps({"type": "chunk", "content": content})}\n\n'
            except Exception as exc:
                logger.exception("Expert model stream failed after escalation")
                yield f'data: {json.dumps({"type": "error", "content": str(exc)})}\n\n'
        else:
            # Resposta direta do modelo leve.
            logger.info("[CHAT] Respondido pelo modelo rápido: %s", fast_model)
            if fast_payload:
                yield f'data: {json.dumps({"type": "chunk", "content": fast_payload})}\n\n'
    else:
        # Fluxo simples: um único modelo recebe o contexto completo.
        single_model_messages = _prepend_system_messages(
            current_messages,
            [system_prompt, session_prompt, extra_context],
        )
        try:
            async for chunk in stream_openrouter(
                messages=single_model_messages,
                model=model,
                max_tokens=4096,
                temperature=0.7,
            ):
                if "choices" not in chunk or not chunk["choices"]:
                    continue
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield f'data: {json.dumps({"type": "chunk", "content": content})}\n\n'
        except Exception as exc:
            logger.exception("Normal chat stream failed")
            yield f'data: {json.dumps({"type": "error", "content": str(exc)})}\n\n'


@router.post("/chat")
async def chat_endpoint(request: Request):
    """
    Endpoint principal de chat com SSE streaming.
    Injeta contexto persistente (preferências, memória, RAG) antes do orquestrador.
    """
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", get_config().openrouter_model)
    mode = body.get("mode", "agent")
    system_prompt = body.get("system_prompt", "")
    session_id = body.get("session_id")
    user_id = body.get("user_id") or None
    project_id = body.get("project_id") or None
    conversation_id = body.get("conversation_id") or None
    web_search = bool(body.get("web_search", False))
    computer_enabled = bool(body.get("computer_enabled", False))
    spy_pages_enabled = bool(body.get("spy_pages_enabled", False))
    fast_model = body.get("fast_model") or None
    fast_system_prompt = body.get("fast_system_prompt", "") or ""
    browser_resume_token = body.get("browser_resume_token") or None

    # GC de sessões em background (throttled a cada 5 min) — não bloqueia o request
    asyncio.ensure_future(asyncio.to_thread(_maybe_run_gc))

    # Extrai última mensagem do usuário para RAG e title
    user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            user_message = content if isinstance(content, str) else str(content)
            break

    execution_logger = ExecutionLogService()

    async def generate():
        collected_content: list[str] = []
        stream_failed = False
        final_error: str | None = None
        awaiting_clarification = False
        conv_id = conversation_id
        execution_id: str | None = None
        normal_agent_id: str | None = None
        enhanced_messages = list(messages)
        extra_context = ""
        web_search_injected = False
        _prompt_t = 0
        _completion_t = 0
        _total_t = 0
        _cost_usd = 0.0
        start_token_tracking()  # inicia acumulação de tokens para esta request

        # Força o start do streaming antes de bater em Supabase/OpenRouter.
        yield ": stream-start\n\n"

        try:
            try:
                extra_context = await asyncio.wait_for(
                    _build_extra_context(user_id, project_id, user_message),
                    timeout=_EXTRA_CONTEXT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[CHAT] Timeout de %ss ao montar contexto extra para user_id=%s",
                    _EXTRA_CONTEXT_TIMEOUT_SECONDS,
                    user_id,
                )
                extra_context = ""
            except Exception:
                logger.exception("[CHAT] Falha inesperada ao montar contexto extra")
                extra_context = ""

            if extra_context and mode != "normal":
                enhanced_messages = [
                    {"role": "system", "content": extra_context},
                    *enhanced_messages,
                ]

            if mode == "normal" and web_search and user_message:
                try:
                    from backend.services.search_service import search_web_formatted

                    search_results = await asyncio.wait_for(
                        search_web_formatted(user_message),
                        timeout=_NORMAL_WEB_SEARCH_TIMEOUT_SECONDS,
                    )
                    if search_results and not search_results.startswith("ERRO") and not search_results.startswith("Erro"):
                        enhanced_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "Resultados de pesquisa web sobre a pergunta do usuário:\n\n"
                                    f"{search_results}\n\n"
                                    "Use essas informações para enriquecer sua resposta. Cite as fontes quando relevante."
                                ),
                            },
                            *enhanced_messages,
                        ]
                        web_search_injected = True
                        logger.info("[CHAT] Web search injetado para modo normal: %s", user_message[:60])
                except asyncio.TimeoutError:
                    logger.warning(
                        "[CHAT] Timeout de %ss ao injetar web search no modo normal",
                        _NORMAL_WEB_SEARCH_TIMEOUT_SECONDS,
                    )
                except Exception as exc:
                    logger.warning("[CHAT] Falha na pesquisa web: %s", exc)

            if conv_id and user_id:
                owned_conversation = await asyncio.to_thread(_get_owned_conversation, conv_id, user_id)
                if not owned_conversation:
                    logger.warning("[CHAT] conversation_id inválido ou sem posse para user_id=%s", user_id)
                    conv_id = None

            if not conv_id and user_id:
                new_conv_id = str(uuid.uuid4())
                try:
                    db = get_supabase_client()
                    now = _now_iso()
                    title = (
                        user_message[:60] + "..."
                        if len(user_message) > 60
                        else user_message or "Nova Conversa"
                    )
                    await asyncio.to_thread(
                        db.insert,
                        "conversations",
                        {
                            "id": new_conv_id,
                            "user_id": user_id,
                            "project_id": project_id,
                            "title": title,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    conv_id = new_conv_id
                except Exception as exc:
                    logger.warning("[CHAT] Falha ao criar conversa: %s", exc)

            execution_id = await execution_logger.create_execution(
                conversation_id=conv_id,
                session_id=session_id,
                project_id=project_id,
                user_id=user_id,
                request_text=user_message,
                request_source=mode,
                supervisor_agent="chat",
                metadata={"model": model, "fast_model": fast_model, "mode": mode},
                model_used=model,
            )

            if conv_id:
                yield f'data: {json.dumps({"type": "conversation_id", "content": conv_id})}\n\n'

            if mode == "normal":
                normal_agent_id = await execution_logger.start_agent(
                    execution_id,
                    agent_key="chat_normal",
                    agent_name="Chat Normal",
                    model=model,
                    role="assistant",
                    route="normal_chat",
                    input_payload={"session_id": session_id},
                )
                await execution_logger.log_event(
                    execution_id,
                    execution_agent_id=normal_agent_id,
                    event_type="normal_chat_started",
                    message="Fluxo de chat normal iniciado",
                    raw_payload={"model": model, "fast_model": fast_model, "session_id": session_id},
                )
                if web_search_injected:
                    await execution_logger.log_event(
                        execution_id,
                        execution_agent_id=normal_agent_id,
                        event_type="web_search_injected",
                        message="Pesquisa web realizada e injetada no contexto",
                        tool_name="web_search",
                        tool_args={"query": user_message[:120]},
                        raw_payload={"web_search": True},
                    )
                stream = _stream_normal_chat(
                    enhanced_messages,
                    model,
                    system_prompt,
                    session_id,
                    fast_model=fast_model,
                    fast_system_prompt=fast_system_prompt,
                    extra_context=extra_context,
                )
            else:
                stream = orchestrate_and_stream(
                    enhanced_messages,
                    model,
                    session_id,
                    user_id=user_id,
                    browser_resume_token=browser_resume_token,
                    computer_enabled=computer_enabled,
                    spy_pages_enabled=spy_pages_enabled,
                    execution_id=execution_id,
                    execution_logger=execution_logger,
                )

            async for event_str in stream:
                yield event_str
                try:
                    if event_str.startswith("data: "):
                        event = json.loads(event_str[6:])
                        if event.get("type") == "chunk":
                            collected_content.append(event.get("content", ""))
                        elif event.get("type") == "error":
                            stream_failed = True
                            final_error = str(event.get("content") or "Erro desconhecido")
                        elif event.get("type") in {"clarification", "needs_clarification"}:
                            awaiting_clarification = True
                except Exception:
                    pass
        except Exception as exc:
            stream_failed = True
            final_error = str(exc)
            logger.exception("[CHAT] Stream generation failed")
            yield f'data: {json.dumps({"type": "error", "content": final_error})}\n\n'
        finally:
            # Soma tokens de chamadas não-stream + stream.
            # No modo agente, o fluxo usa ambos; priorizar só stream subconta o custo real.
            _usage = get_token_usage()
            _prompt_t = int(_usage.get("prompt_tokens", 0) or 0) + int(_usage.get("stream_prompt_tokens", 0) or 0)
            _completion_t = int(_usage.get("completion_tokens", 0) or 0) + int(_usage.get("stream_completion_tokens", 0) or 0)
            _total_t = int(_usage.get("total_tokens", 0) or 0) + int(_usage.get("stream_total_tokens", 0) or 0)
            try:
                _cost_usd = await estimate_cost(model, _prompt_t, _completion_t)
            except Exception:
                _cost_usd = 0.0

            if normal_agent_id:
                await execution_logger.log_event(
                    execution_id,
                    execution_agent_id=normal_agent_id,
                    level="error" if stream_failed else "info",
                    event_type="normal_chat_finished",
                    message=final_error or "Fluxo de chat normal finalizado",
                    raw_payload={"response_preview": "".join(collected_content)[:1500]},
                )
                await execution_logger.finish_agent(
                    normal_agent_id,
                    status="awaiting_clarification" if awaiting_clarification else ("failed" if stream_failed else "completed"),
                    output_payload={"response_preview": "".join(collected_content)[:1500]},
                    error_text=final_error,
                    prompt_tokens=_prompt_t,
                    completion_tokens=_completion_t,
                    total_tokens=_total_t,
                    estimated_cost_usd=_cost_usd,
                )
            await execution_logger.finish_execution(
                execution_id,
                status="awaiting_clarification" if awaiting_clarification else ("failed" if stream_failed else "completed"),
                final_error=final_error,
                metadata={"response_length": len("".join(collected_content))},
                total_tokens=_total_t,
                total_cost_usd=_cost_usd,
            )
            if conv_id and user_id and (user_message or collected_content):
                full_response = "".join(collected_content)
                try:
                    await _save_conversation_and_update_memory(
                        conv_id=conv_id,
                        user_id=user_id,
                        user_message=user_message,
                        assistant_response=full_response,
                        prompt_tokens=_prompt_t,
                        completion_tokens=_completion_t,
                        total_tokens=_total_t,
                        cost_usd=_cost_usd,
                    )
                except Exception:
                    logger.exception("[CHAT] Falha ao persistir histórico ao final do stream")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
