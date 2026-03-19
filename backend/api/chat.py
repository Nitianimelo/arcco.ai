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

NOTA: O system_prompt enviado pelo frontend é IGNORADO intencionalmente.
Os prompts de cada agente estão em backend/agents/prompts.py.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agents.orchestrator import orchestrate_and_stream
from backend.core.llm import stream_openrouter
from backend.core.supabase_client import get_supabase_client
from backend.services.session_gc_service import cleanup_expired_sessions
from backend.services.session_file_service import get_session_inventory, touch_session
from backend.services.chat_models import list_chat_models
from backend.services.memory_service import get_user_memory, update_user_memory
from backend.services.project_rag_service import search_project_context

logger = logging.getLogger(__name__)
router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/chat-models")
async def get_public_chat_models():
    models = [item for item in list_chat_models() if item.get("is_active")]
    return {"models": models}


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
        if rows and rows[0].get("custom_instructions"):
            parts.append(
                f"Instruções personalizadas do usuário:\n{rows[0]['custom_instructions']}"
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
                db.query, "projects", "*", {"id": project_id}
            )
            if rows and rows[0].get("instructions"):
                parts.append(f"Instruções do projeto ativo:\n{rows[0]['instructions']}")
        except Exception as e:
            logger.warning(f"[CHAT] Falha ao buscar instruções do projeto: {e}")

        # RAG — contexto relevante da base de conhecimento (sync → thread)
        try:
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
                }
            )
        if assistant_response:
            messages_to_save.append(
                {
                    "conversation_id": conv_id,
                    "role": "assistant",
                    "content": assistant_response,
                    "created_at": now,
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


async def _stream_normal_chat(messages: list, model: str, system_prompt: str, session_id: str | None):
    current_messages = list(messages)
    system_messages = []
    if system_prompt:
        system_messages.append({"role": "system", "content": system_prompt})
    session_prompt = _build_session_inventory_prompt(session_id)
    if session_prompt:
        system_messages.append({"role": "system", "content": session_prompt})
    if system_messages:
        current_messages = [*system_messages, *current_messages]

    try:
        async for chunk in stream_openrouter(
            messages=current_messages,
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
    model = body.get("model", "anthropic/claude-3.5-sonnet")
    mode = body.get("mode", "agent")
    system_prompt = body.get("system_prompt", "")
    session_id = body.get("session_id")
    user_id = body.get("user_id") or None
    project_id = body.get("project_id") or None
    conversation_id = body.get("conversation_id") or None

    cleanup_expired_sessions()

    # Extrai última mensagem do usuário para RAG e title
    user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            content = msg.get("content", "")
            user_message = content if isinstance(content, str) else str(content)
            break

    # Monta contexto extra (preferências, memória, projeto, RAG)
    extra_context = await _build_extra_context(user_id, project_id, user_message)

    # Injeta como mensagem system no início
    enhanced_messages = list(messages)
    if extra_context:
        enhanced_messages = [
            {"role": "system", "content": extra_context},
            *enhanced_messages,
        ]

    # Determina/cria conversation_id
    conv_id = conversation_id
    if not conv_id and user_id:
        conv_id = str(uuid.uuid4())
        try:
            db = get_supabase_client()
            now = _now_iso()
            title = (
                user_message[:60] + "..."
                if len(user_message) > 60
                else user_message or "Nova Conversa"
            )
            db.insert(
                "conversations",
                {
                    "id": conv_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "title": title,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except Exception as e:
            logger.warning(f"[CHAT] Falha ao criar conversa: {e}")

    async def generate():
        collected_content: list[str] = []

        # Emite conversation_id como primeiro evento SSE
        if conv_id:
            yield f'data: {json.dumps({"type": "conversation_id", "content": conv_id})}\n\n'

        stream = (
            _stream_normal_chat(enhanced_messages, model, system_prompt, session_id)
            if mode == "normal"
            else orchestrate_and_stream(enhanced_messages, model, session_id)
        )

        async for event_str in stream:
            yield event_str
            # Coleta chunks para salvar no histórico
            try:
                if event_str.startswith("data: "):
                    event = json.loads(event_str[6:])
                    if event.get("type") == "chunk":
                        collected_content.append(event.get("content", ""))
            except Exception:
                pass

        # Dispara background task ao fim do stream
        if conv_id and user_id and (user_message or collected_content):
            full_response = "".join(collected_content)
            asyncio.ensure_future(
                _save_conversation_and_update_memory(
                    conv_id=conv_id,
                    user_id=user_id,
                    user_message=user_message,
                    assistant_response=full_response,
                )
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
