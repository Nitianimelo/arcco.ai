"""
Endpoint de chat — Arquitetura Multi-Agente com Orquestrador.

POST /api/agent/chat
  → Orquestrador analisa a mensagem e determina a rota
  → Especialista executa (apenas com suas ferramentas)
  → QA revisa a saída (máx. 2 tentativas)
  → Resposta final via SSE streaming

Modos:
  Chat Normal  → route 'chat': assistente direto, sem ferramentas, sem QA
  Modo Agente  → route web_search | file_generator | design | dev

NOTA: O system_prompt enviado pelo frontend é IGNORADO intencionalmente.
Os prompts de cada agente estão em backend/agents/prompts.py.
"""

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.agents.orchestrator import orchestrate_and_stream
from backend.core.llm import stream_openrouter
from backend.services.session_gc_service import cleanup_expired_sessions
from backend.services.session_file_service import get_session_inventory, touch_session
from backend.services.chat_models import list_chat_models

logger = logging.getLogger(__name__)
router = APIRouter()


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
    O Orquestrador determina automaticamente o especialista correto.
    """
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "anthropic/claude-3.5-sonnet")
    mode = body.get("mode", "agent")
    system_prompt = body.get("system_prompt", "")
    session_id = body.get("session_id")

    cleanup_expired_sessions()

    stream = (
        _stream_normal_chat(messages, model, system_prompt, session_id)
        if mode == "normal"
        else orchestrate_and_stream(messages, model, session_id)
    )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
