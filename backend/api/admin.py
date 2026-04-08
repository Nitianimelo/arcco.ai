"""
Endpoints do Painel Administrativo.

ROTAS DISPONÍVEIS:
  GET  /api/admin/agents              → Lista todos os agentes com configs atuais
  GET  /api/admin/agents/{id}         → Detalhe de um agente específico
  PUT  /api/admin/agents/{id}         → Salva alterações diretamente nos arquivos .py + memória
  POST /api/admin/agents/reset/{id}   → Reseta agente para os valores padrão do código
  GET  /api/admin/models              → Lista todos os modelos do OpenRouter com preços

COMO AS ALTERAÇÕES SÃO SALVAS:
  - system_prompt → reescrito com regex diretamente em prompts.py
  - tools         → reescrito com AST (análise de código) diretamente em tools.py
  - model         → salvo no override JSON (não existe constante .py para modelo)
  - name/description → apenas em memória/JSON (não ficam nos .py)

  Uvicorn com --reload detecta mudanças nos .py e reinicia o servidor automaticamente.
"""

import ast
import hashlib
import json
import logging
import re
import secrets
import time
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from backend.agents import registry
from backend.services.agent_model_overrides import delete_agent_model_override, save_agent_model_override
from backend.services.chat_models import create_chat_model, delete_chat_model, list_chat_models, update_chat_model
from backend.services.execution_log_service import get_execution_details, list_execution_summaries

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Auth do painel admin ───────────────────────────────────────────────────────

def _admin_token() -> str:
    """Gera token determinístico a partir das credenciais. Nunca exposto ao frontend."""
    from backend.core.config import get_config
    cfg = get_config()
    if not cfg.admin_username or not cfg.admin_password:
        raise HTTPException(status_code=503, detail="Painel admin não configurado no ambiente")
    return hashlib.sha256(f"{cfg.admin_username}:{cfg.admin_password}:arcco_admin".encode()).hexdigest()


async def verify_admin(authorization: str = Header(default="")) -> None:
    """Dependency FastAPI — valida Bearer token em todas as rotas protegidas."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de admin necessário")
    token = authorization[7:]
    if not secrets.compare_digest(token, _admin_token()):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def admin_login(req: LoginRequest):
    """Rota pública — valida usuário/senha e retorna o token de sessão."""
    from backend.core.config import get_config
    cfg = get_config()
    if not cfg.admin_username or not cfg.admin_password:
        raise HTTPException(status_code=503, detail="Painel admin não configurado no ambiente")
    valid_user = secrets.compare_digest(req.username, cfg.admin_username)
    valid_pass = secrets.compare_digest(req.password, cfg.admin_password)
    if not (valid_user and valid_pass):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    return {"token": _admin_token()}

# ── Caminhos dos arquivos-fonte dos agentes ───────────────────────────────────

_PROMPTS_FILE = Path(__file__).parent.parent / "agents" / "prompts.py"
_TOOLS_FILE   = Path(__file__).parent.parent / "agents" / "tools.py"

# Mapeamento: agent_id → nome da constante Python em prompts.py
_PROMPT_CONSTANTS: dict[str, str] = {
    "chat":           "CHAT_SYSTEM_PROMPT",
    "web_search":     "WEB_SEARCH_SYSTEM_PROMPT",
    "text_generator": "TEXT_GENERATOR_SYSTEM_PROMPT",
    "design_generator": "DESIGN_GENERATOR_SYSTEM_PROMPT",
    "file_modifier":  "FILE_MODIFIER_SYSTEM_PROMPT",
    "qa":             "QA_SYSTEM_PROMPT",
    "planner":        "PLANNER_SYSTEM_PROMPT",
}

# Mapeamento: agent_id → nome da constante Python em tools.py
# Apenas agentes que têm ferramentas definidas como lista no tools.py
_TOOLS_CONSTANTS: dict[str, str] = {
    "chat":           "SUPERVISOR_TOOLS",
    "web_search":     "WEB_SEARCH_TOOLS",
    "text_generator": "TEXT_GENERATOR_TOOLS",
    "design_generator": "DESIGN_GENERATOR_TOOLS",
    "file_modifier":  "FILE_MODIFIER_TOOLS",
}


# ── Escrita nos arquivos .py ───────────────────────────────────────────────────

def _write_prompt_to_source(agent_id: str, new_prompt: str) -> None:
    """
    Reescreve a constante de system prompt diretamente em prompts.py usando regex.

    Estratégia regex:
      - Localiza `CONSTANTE = \"\"\"...\"\"\"` com flag DOTALL (span múltiplas linhas)
      - Padrão não-greedy (.*?) para não capturar além da primeira constante
      - Triple-quotes internas no prompt são convertidas para ''' para não quebrar
    """
    constant = _PROMPT_CONSTANTS.get(agent_id)
    if not constant:
        return  # Agente sem constante mapeada — nada a fazer

    content = _PROMPTS_FILE.read_text(encoding="utf-8-sig")

    # Garante que o conteúdo não contenha triple-quotes que quebrariam o Python
    safe_prompt = new_prompt.replace('"""', "'''")

    # Regex que encontra: CONSTANTE = f?"""qualquer coisa"""
    pattern = re.compile(
        rf'^{re.escape(constant)}\s*=\s*(?:f)?""".*?"""',
        re.MULTILINE | re.DOTALL,
    )

    replacement = f'{constant} = """{safe_prompt}"""'
    new_content, count = re.subn(pattern, replacement, content)

    if count == 0:
        raise ValueError(f"Constante '{constant}' não encontrada em prompts.py")

    _PROMPTS_FILE.write_text(new_content, encoding="utf-8")
    logger.info(f"[ADMIN] prompts.py → '{constant}' atualizado")


def _write_tools_to_source(agent_id: str, new_tools: list) -> None:
    """
    Reescreve a constante de tools diretamente em tools.py usando o módulo ast.

    Por que AST em vez de regex?
    - Tools são listas Python com estrutura complexa (dicts aninhados)
    - AST localiza exatamente as linhas start/end da atribuição, sem risco de
      capturar conteúdo demais como poderia acontecer com regex
    - O novo valor é serializado como JSON (válido como Python literal)

    Agentes sem tools mapeados (chat, design, dev, qa) são silenciosamente ignorados.
    """
    constant = _TOOLS_CONSTANTS.get(agent_id)
    if not constant:
        return  # Agente não tem tools no tools.py — silencioso

    content = _TOOLS_FILE.read_text(encoding="utf-8-sig")
    lines = content.split("\n")

    tree = ast.parse(content)
    found = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == constant):
                continue

            # ast usa linhas 1-indexed; convertemos para 0-indexed
            start = node.lineno - 1   # primeira linha da atribuição
            end   = node.end_lineno   # última linha (exclusive ao fatiar)

            # JSON é um subset válido de Python para listas/dicts
            formatted = json.dumps(new_tools, ensure_ascii=False, indent=4)
            new_assignment = f"{constant} = {formatted}"

            # Substitui as linhas da constante pelo novo valor
            new_lines = lines[:start] + [new_assignment] + lines[end:]
            _TOOLS_FILE.write_text("\n".join(new_lines), encoding="utf-8")
            logger.info(f"[ADMIN] tools.py → '{constant}' atualizado")
            found = True
            break
        if found:
            break

    if not found:
        raise ValueError(f"Constante '{constant}' não encontrada em tools.py")


# ── Cache de modelos OpenRouter ────────────────────────────────────────────────
# A lista de modelos muda pouco — cache de 1 hora evita chamadas repetidas à API

_models_cache: list | None = None
_models_cache_ts: float = 0
_MODELS_CACHE_TTL = 3600  # segundos (1 hora)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/agents", dependencies=[Depends(verify_admin)])
async def list_agents():
    """Lista todos os agentes com suas configurações atuais (memória + overrides)."""
    return {"agents": registry.get_all()}


@router.post("/agents/reload-models", dependencies=[Depends(verify_admin)])
async def reload_agent_models():
    """Recarrega os modelos dos agentes a partir do Supabase sem tocar em prompts/tools."""
    agents = registry.reload_models_from_supabase()
    return {"success": True, "agents": agents}


@router.get("/executions", dependencies=[Depends(verify_admin)])
async def list_executions(limit: int = 100):
    """Lista execuções recentes do sistema para o painel admin."""
    rows = await list_execution_summaries(limit=limit)
    return {"executions": rows}


@router.get("/executions/{execution_id}", dependencies=[Depends(verify_admin)])
async def execution_details(execution_id: str):
    """Retorna execução principal + agentes + logs detalhados."""
    result = await get_execution_details(execution_id)
    if not result.get("execution"):
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return result


@router.get("/agents/{agent_id}", dependencies=[Depends(verify_admin)])
async def get_agent(agent_id: str):
    """Retorna a configuração atual de um agente específico."""
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' não encontrado")
    return agent


@router.put("/agents/{agent_id}", dependencies=[Depends(verify_admin)])
async def update_agent(agent_id: str, req: "AgentUpdateRequest"):
    """
    Salva alterações de um agente.

    O que cada campo faz:
      system_prompt → reescrito com regex em prompts.py (mudança permanente no código)
      tools         → reescrito com AST em tools.py (mudança permanente no código)
      model         → salvo no Supabase e refletido em memória
      name/desc     → apenas em memória e JSON override

    Erros parciais são coletados e retornados juntos ao final.
    Uvicorn --reload detecta as mudanças nos .py e reinicia automaticamente.
    """
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' não encontrado")

    errors: list[str] = []
    update_data: dict[str, Any] = {}
    supports_prompt_edit = bool(agent.get("supports_prompt_edit", True))
    supports_tools_edit = bool(agent.get("supports_tools_edit", True))

    if req.system_prompt is not None:
        if supports_prompt_edit:
            try:
                _write_prompt_to_source(agent_id, req.system_prompt)
                update_data["system_prompt"] = req.system_prompt
            except Exception as e:
                errors.append(f"prompt: {e}")
        else:
            update_data["system_prompt"] = agent.get("system_prompt", "")

    if req.tools is not None:
        if supports_tools_edit:
            try:
                _write_tools_to_source(agent_id, req.tools)
                update_data["tools"] = req.tools
            except Exception as e:
                errors.append(f"tools: {e}")
        else:
            update_data["tools"] = agent.get("tools", [])

    if req.model is not None:
        try:
            normalized_model = req.model.strip()
            if not normalized_model:
                raise ValueError("model vazio")
            save_agent_model_override(agent_id, normalized_model)
            update_data["model"] = normalized_model
            update_data["model_source"] = "supabase"
        except Exception as e:
            errors.append(f"model_supabase: {e}")

    if req.name is not None:
        update_data["name"] = req.name

    if req.description is not None:
        update_data["description"] = req.description

    # Aplica todas as mudanças válidas em memória + JSON override
    if update_data:
        registry.update_agent(agent_id, update_data)

    # Se houve erro em algum campo, reporta tudo de uma vez
    if errors:
        raise HTTPException(status_code=500, detail="; ".join(errors))

    logger.info(f"[ADMIN] Agente '{agent_id}' salvo no código-fonte")
    return {"success": True, "agent": registry.get_agent(agent_id)}


@router.post("/agents/reset/{agent_id}", dependencies=[Depends(verify_admin)])
async def reset_agent(agent_id: str):
    """
    Reseta o agente para os valores padrão definidos nos arquivos .py.

    Reimporta os prompts/tools diretamente dos arquivos-fonte — útil depois
    de testar mudanças e querer voltar ao estado original.
    Não reescreve os .py; apenas atualiza memória e override JSON.
    """
    from backend.agents.prompts import (
        CHAT_SYSTEM_PROMPT,
        WEB_SEARCH_SYSTEM_PROMPT, TEXT_GENERATOR_SYSTEM_PROMPT, DESIGN_GENERATOR_SYSTEM_PROMPT,
        FILE_MODIFIER_SYSTEM_PROMPT, QA_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT,
    )
    from backend.agents.tools import SUPERVISOR_TOOLS, WEB_SEARCH_TOOLS, TEXT_GENERATOR_TOOLS, DESIGN_GENERATOR_TOOLS, FILE_MODIFIER_TOOLS
    from backend.core.config import get_config

    default_model = get_config().openrouter_model

    DEFAULTS: dict[str, dict] = {
        "chat":           {"system_prompt": CHAT_SYSTEM_PROMPT,           "model": default_model, "tools": SUPERVISOR_TOOLS},
        "web_search":     {"system_prompt": WEB_SEARCH_SYSTEM_PROMPT,     "model": default_model, "tools": WEB_SEARCH_TOOLS},
        "text_generator": {"system_prompt": TEXT_GENERATOR_SYSTEM_PROMPT, "model": default_model, "tools": TEXT_GENERATOR_TOOLS},
        "design_generator": {"system_prompt": DESIGN_GENERATOR_SYSTEM_PROMPT, "model": default_model, "tools": DESIGN_GENERATOR_TOOLS},
        "file_modifier":  {"system_prompt": FILE_MODIFIER_SYSTEM_PROMPT,  "model": default_model, "tools": FILE_MODIFIER_TOOLS},
        "qa":             {"system_prompt": QA_SYSTEM_PROMPT,             "model": default_model, "tools": []},
        "planner":        {"system_prompt": PLANNER_SYSTEM_PROMPT,        "model": "openai/gpt-4o-mini", "tools": []},
        "deep_research":  {"system_prompt": "",                           "model": default_model, "tools": []},
        "memory":         {"system_prompt": "",                           "model": "openai/gpt-4o-mini", "tools": []},
        "intent_router":  {"system_prompt": "",                           "model": "openai/gpt-4o-mini", "tools": []},
    }

    if agent_id not in DEFAULTS:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' não encontrado")

    try:
        delete_agent_model_override(agent_id)
    except Exception as e:
        logger.warning(f"[ADMIN] Falha ao limpar override de modelo no Supabase para '{agent_id}': {e}")

    registry.update_agent(agent_id, {**DEFAULTS[agent_id], "model_source": "local"})
    return {"success": True, "agent": registry.get_agent(agent_id)}


@router.get("/models", dependencies=[Depends(verify_admin)])
async def list_models():
    """
    Retorna todos os modelos disponíveis no OpenRouter com preços por 1M de tokens.

    Ordenação: modelos pagos primeiro (por nome), gratuitos por último.
    Cache de 1 hora para não sobrecarregar a API do OpenRouter.

    Campos retornados por modelo:
      id             → identificador usado na API (ex: "openai/gpt-4o")
      name           → nome legível (ex: "OpenAI: GPT-4o")
      context_length → janela de contexto em tokens
      pricing        → { prompt_1m, completion_1m } — custo por 1 milhão de tokens em USD
    """
    global _models_cache, _models_cache_ts

    # Retorna do cache se ainda válido
    if _models_cache and (time.time() - _models_cache_ts) < _MODELS_CACHE_TTL:
        return {"models": _models_cache, "cached": True}

    from backend.core.config import get_config
    config = get_config()

    headers: dict[str, str] = {
        "HTTP-Referer": "https://arcco.ai",
        "X-Title": "Arcco Admin",
    }
    if config.openrouter_api_key:
        headers["Authorization"] = f"Bearer {config.openrouter_api_key}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar modelos do OpenRouter: {e}")

    models = []
    for m in data.get("data", []):
        pricing = m.get("pricing", {})
        try:
            # OpenRouter retorna preço por token; multiplicamos por 1M para exibir
            prompt_1m     = round(float(pricing.get("prompt", 0) or 0) * 1_000_000, 4)
            completion_1m = round(float(pricing.get("completion", 0) or 0) * 1_000_000, 4)
        except (ValueError, TypeError):
            prompt_1m = completion_1m = 0.0

        models.append({
            "id":             m["id"],
            "name":           m.get("name", m["id"]),
            "context_length": m.get("context_length", 0),
            "pricing": {
                "prompt_1m":     prompt_1m,
                "completion_1m": completion_1m,
            },
        })

    # Gratuitos (ambos os preços = 0) vão para o final da lista
    models.sort(key=lambda x: (
        x["pricing"]["prompt_1m"] == 0 and x["pricing"]["completion_1m"] == 0,
        x["name"].lower()
    ))

    _models_cache    = models
    _models_cache_ts = time.time()

    logger.info(f"[ADMIN] {len(models)} modelos carregados do OpenRouter")
    return {"models": models, "cached": False}


@router.get("/chat-models", dependencies=[Depends(verify_admin)])
async def get_chat_models():
    return {"models": list_chat_models(force_refresh=True)}


@router.post("/chat-models", dependencies=[Depends(verify_admin)])
async def post_chat_model(req: "ChatModelRequest"):
    created = create_chat_model(req.model_dump())
    return {"success": True, "model": created}


@router.put("/chat-models/{model_id}", dependencies=[Depends(verify_admin)])
async def put_chat_model(model_id: str, req: "ChatModelRequest"):
    updated = update_chat_model(model_id, req.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Modelo de chat nao encontrado")
    return {"success": True, "model": updated}


@router.delete("/chat-models/{model_id}", dependencies=[Depends(verify_admin)])
async def remove_chat_model(model_id: str):
    deleted = delete_chat_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Modelo de chat nao encontrado")
    return {"success": True}


# ── Schema de entrada ──────────────────────────────────────────────────────────
# Definido após os endpoints para evitar NameError nas type hints acima.
# FastAPI resolve anotações como string ("AgentUpdateRequest") em tempo de execução.

class AgentUpdateRequest(BaseModel):
    system_prompt: Optional[str] = None   # Novo system prompt (reescrito em prompts.py)
    model:         Optional[str] = None   # ID do modelo OpenRouter
    tools:         Optional[list[Any]] = None  # Lista de tools no formato OpenAI
    name:          Optional[str] = None   # Nome de exibição do agente
    description:   Optional[str] = None  # Descrição curta do agente

class ChatModelRequest(BaseModel):
    model_name: str = ""
    openrouter_model_id: str = ""
    fast_model_id: str = ""
    fast_system_prompt: str = ""
    system_prompt: str = ""
    is_active: bool = True
    slot_number: Optional[int] = None


# ── Endpoints de Token Usage / Custos ─────────────────────────────────────────

def _parse_days_filter(days: int) -> str | None:
    """Retorna ISO timestamp de corte para filtrar por período."""
    if days <= 0:
        return None
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.isoformat()


@router.get("/token-usage/summary", dependencies=[Depends(verify_admin)])
async def token_usage_summary(days: int = 30, mode: str = "all"):
    """
    Resumo completo de uso de tokens e custo estimado.
    Retorna: totais gerais, por modo (normal/agente), por modelo (top 10),
             por dia (últimos N dias), por usuário (top 20).
    """
    import asyncio as _asyncio
    from backend.core.supabase_client import get_supabase_client

    cutoff = _parse_days_filter(days)
    client = get_supabase_client()

    try:
        # Busca execuções no período
        rows = await _asyncio.to_thread(
            client.query,
            "agent_executions",
            "id,user_id,request_source,model_used,total_tokens,total_cost_usd,created_at,status",
            None,
            "created_at.desc",
            5000,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar execuções: {exc}")

    # Filtra por período em Python (PostgREST não suporta gte sem SDK completo)
    if cutoff:
        rows = [r for r in rows if (r.get("created_at") or "") >= cutoff]

    if mode != "all":
        rows = [r for r in rows if (r.get("request_source") or "agent") == mode]

    total_tokens = sum(r.get("total_tokens") or 0 for r in rows)
    total_cost   = sum(float(r.get("total_cost_usd") or 0) for r in rows)
    total_execs  = len(rows)

    # Por modo (request_source: "normal" vs "agent")
    by_mode: dict[str, dict] = {}
    for r in rows:
        mode = r.get("request_source") or "agent"
        if mode not in by_mode:
            by_mode[mode] = {"mode": mode, "tokens": 0, "cost": 0.0, "count": 0}
        by_mode[mode]["tokens"] += r.get("total_tokens") or 0
        by_mode[mode]["cost"]   += float(r.get("total_cost_usd") or 0)
        by_mode[mode]["count"]  += 1

    # Por modelo (top 10)
    by_model: dict[str, dict] = {}
    for r in rows:
        mdl = r.get("model_used") or "desconhecido"
        if mdl not in by_model:
            by_model[mdl] = {"model": mdl, "tokens": 0, "cost": 0.0, "count": 0}
        by_model[mdl]["tokens"] += r.get("total_tokens") or 0
        by_model[mdl]["cost"]   += float(r.get("total_cost_usd") or 0)
        by_model[mdl]["count"]  += 1
    top_models = sorted(by_model.values(), key=lambda x: x["cost"], reverse=True)[:10]

    # Por dia
    by_day: dict[str, dict] = {}
    for r in rows:
        day = (r.get("created_at") or "")[:10]  # YYYY-MM-DD
        if not day:
            continue
        if day not in by_day:
            by_day[day] = {"date": day, "tokens": 0, "cost": 0.0, "count": 0}
        by_day[day]["tokens"] += r.get("total_tokens") or 0
        by_day[day]["cost"]   += float(r.get("total_cost_usd") or 0)
        by_day[day]["count"]  += 1
    days_list = sorted(by_day.values(), key=lambda x: x["date"], reverse=True)

    # Por usuário (top 20)
    by_user: dict[str, dict] = {}
    for r in rows:
        uid = r.get("user_id") or "anônimo"
        if uid not in by_user:
            by_user[uid] = {"user_id": uid, "tokens": 0, "cost": 0.0, "count": 0}
        by_user[uid]["tokens"] += r.get("total_tokens") or 0
        by_user[uid]["cost"]   += float(r.get("total_cost_usd") or 0)
        by_user[uid]["count"]  += 1
    top_users = sorted(by_user.values(), key=lambda x: x["cost"], reverse=True)[:20]

    return {
        "period_days": days,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "total_executions": total_execs,
        "avg_cost_per_execution": round(total_cost / total_execs, 6) if total_execs else 0,
        "by_mode": list(by_mode.values()),
        "by_model": top_models,
        "by_day": days_list,
        "by_user": top_users,
    }


@router.get("/token-usage/executions", dependencies=[Depends(verify_admin)])
async def token_usage_executions(limit: int = 200, mode: str = "all", days: int = 30):
    """
    Lista execuções com tokens e custo, filtráveis por modo e período.
    mode: 'all' | 'normal' | 'agent'
    """
    import asyncio as _asyncio
    from backend.core.supabase_client import get_supabase_client

    cutoff = _parse_days_filter(days)
    client = get_supabase_client()

    try:
        rows = await _asyncio.to_thread(
            client.query,
            "agent_executions",
            "id,user_id,request_source,model_used,total_tokens,total_cost_usd,status,request_text,created_at,finished_at",
            None,
            "created_at.desc",
            min(limit * 3, 3000),  # busca mais para compensar filtros em Python
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar execuções: {exc}")

    if cutoff:
        rows = [r for r in rows if (r.get("created_at") or "") >= cutoff]
    if mode != "all":
        rows = [r for r in rows if (r.get("request_source") or "agent") == mode]

    return {"executions": rows[:limit], "total": len(rows)}
