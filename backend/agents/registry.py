"""
Registry de configuraÃ§Ã£o dos agentes.

ARQUITETURA DE PERSISTÃŠNCIA (4 camadas):
  1. MemÃ³ria (_REGISTRY)       â†’ acesso instantÃ¢neo durante a execuÃ§Ã£o
  2. Supabase (model)          â†’ fonte principal dos modelos dos agentes
  3. configs_override.json     â†’ backup local / fallback
  4. prompts.py / tools.py     â†’ mudanÃ§a permanente no cÃ³digo-fonte (feita via admin.py)

FLUXO DE INICIALIZAÃ‡ÃƒO:
  initialize() â†’ carrega defaults dos arquivos .py â†’ aplica overrides do JSON

IMPORTANTE: os imports de prompts/tools/config ficam DENTRO de initialize()
para evitar importaÃ§Ã£o circular (orchestrator.py tambÃ©m importa registry).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Arquivo JSON que guarda as customizaÃ§Ãµes feitas pelo admin (model, prompt, tools).
# Fica na mesma pasta deste arquivo: backend/agents/configs_override.json
_OVERRIDE_FILE = Path(__file__).parent / "configs_override.json"

# DicionÃ¡rio principal: agent_id â†’ configuraÃ§Ã£o completa do agente
_REGISTRY: dict[str, dict[str, Any]] = {}

# Flag para inicializaÃ§Ã£o lazy â€” evita carregar tudo no import do mÃ³dulo
_initialized = False


# â”€â”€ InicializaÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def initialize():
    """
    Popula o registry com os valores padrÃ£o dos arquivos .py e entÃ£o
    aplica qualquer override que tenha sido salvo pelo admin.

    Chamado automaticamente no startup do FastAPI (backend/main.py).
    TambÃ©m pode ser chamado manualmente se necessÃ¡rio.
    """
    global _REGISTRY, _initialized

    # Imports locais para evitar circular: este mÃ³dulo Ã© importado por orchestrator,
    # e orchestrator Ã© importado por outros mÃ³dulos que tambÃ©m importam registry.
    from backend.agents.prompts import (
        CHAT_SYSTEM_PROMPT,
        WEB_SEARCH_SYSTEM_PROMPT,
        TEXT_GENERATOR_SYSTEM_PROMPT,
        DESIGN_GENERATOR_SYSTEM_PROMPT,
        FILE_MODIFIER_SYSTEM_PROMPT,
        QA_SYSTEM_PROMPT,
        PLANNER_SYSTEM_PROMPT,
    )
    from backend.agents.tools import (
        SUPERVISOR_TOOLS,
        WEB_SEARCH_TOOLS,
        TEXT_GENERATOR_TOOLS,
        DESIGN_GENERATOR_TOOLS,
        FILE_MODIFIER_TOOLS,
    )
    from backend.core.config import get_config

    default_model = get_config().openrouter_model

    # ConfiguraÃ§Ã£o padrÃ£o de cada agente.
    # "module" agrupa agentes por produto (Arcco Chat, Builder, Pages, Sistema).
    _REGISTRY = {
        "chat": {
            "id": "chat",
            "name": "Orquestrador Supervisor",
            "module": "Arcco Chat",
            "description": "Componente principal de orquestraÃ§Ã£o do modo agente. No runtime ele atua como supervisor e orquestrador.",
            "system_prompt": CHAT_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": SUPERVISOR_TOOLS,
            "runtime_keys": ["chat", "orchestrator", "supervisor"],
            "supports_prompt_edit": True,
            "supports_tools_edit": True,
        },

        "web_search": {
            "id": "web_search",
            "name": "Agente de Busca Web",
            "module": "Arcco Chat",
            "description": "Pesquisa informaÃ§Ãµes na internet via Tavily e lÃª pÃ¡ginas especÃ­ficas",
            "system_prompt": WEB_SEARCH_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": WEB_SEARCH_TOOLS,
            "runtime_keys": ["web_search"],
            "supports_prompt_edit": True,
            "supports_tools_edit": True,
        },
        "text_generator": {
            "id": "text_generator",
            "name": "Gerador de Texto Bruto",
            "module": "Arcco Chat",
            "description": "Cria documentos brutos em texto para preview editavel e exportacao posterior",
            "system_prompt": TEXT_GENERATOR_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": TEXT_GENERATOR_TOOLS,
            "runtime_keys": ["text_generator"],
            "supports_prompt_edit": True,
            "supports_tools_edit": True,
        },
        "design_generator": {
            "id": "design_generator",
            "name": "Gerador de Design",
            "module": "Arcco Chat",
            "description": "Cria HTML visual e editavel para exportacao posterior em imagem, PDF ou PPTX",
            "system_prompt": DESIGN_GENERATOR_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": DESIGN_GENERATOR_TOOLS,
            "runtime_keys": ["design_generator"],
            "supports_prompt_edit": True,
            "supports_tools_edit": True,
        },
        "file_modifier": {
            "id": "file_modifier",
            "name": "Modificador de Arquivos",
            "module": "Arcco Chat",
            "description": "Edita arquivos existentes (PDF, Excel, PPTX) conforme solicitaÃ§Ã£o",
            "system_prompt": FILE_MODIFIER_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": FILE_MODIFIER_TOOLS,
            "runtime_keys": ["file_modifier"],
            "supports_prompt_edit": True,
            "supports_tools_edit": True,
        },
        "qa": {
            "id": "qa",
            "name": "Agente QA",
            "module": "Sistema",
            "description": "Revisa e aprova a qualidade das respostas dos especialistas",
            "system_prompt": QA_SYSTEM_PROMPT,
            "model": default_model,
            "model_source": "local",
            "tools": [],
            "runtime_keys": ["qa"],
            "supports_prompt_edit": True,
            "supports_tools_edit": False,
        },
        "planner": {
            "id": "planner",
            "name": "Planejador de Execução",
            "module": "Sistema",
            "description": "Analisa o pedido do usuário e gera um plano de execução JSON. Usa modelo pequeno e rápido para economizar tokens.",
            "system_prompt": PLANNER_SYSTEM_PROMPT,
            "model": "openai/gpt-4o-mini",
            "model_source": "local",
            "tools": [],
            "runtime_keys": ["planner"],
            "supports_prompt_edit": True,
            "supports_tools_edit": False,
        },
        "deep_research": {
            "id": "deep_research",
            "name": "Pesquisa Profunda",
            "module": "Arcco Chat",
            "description": "Pipeline de pesquisa multi-etapa com planejamento, coleta, sumarizaÃ§Ã£o e sÃ­ntese final.",
            "system_prompt": "",
            "model": default_model,
            "model_source": "local",
            "tools": [],
            "runtime_keys": ["deep_research"],
            "supports_prompt_edit": False,
            "supports_tools_edit": False,
        },
        "memory": {
            "id": "memory",
            "name": "MemÃ³ria do UsuÃ¡rio",
            "module": "Sistema",
            "description": "Atualiza a memÃ³ria acumulada do usuÃ¡rio em background apÃ³s as conversas. ConfiguraÃ§Ã£o exposta apenas para o modelo.",
            "system_prompt": "",
            "model": "openai/gpt-4o-mini",
            "model_source": "local",
            "tools": [],
            "runtime_keys": ["memory", "user_memory"],
            "supports_prompt_edit": False,
            "supports_tools_edit": False,
        },
        "intent_router": {
            "id": "intent_router",
            "name": "Roteador de IntenÃ§Ã£o",
            "module": "Sistema",
            "description": "Classificador leve usado no endpoint de roteamento para decidir a intenÃ§Ã£o da mensagem.",
            "system_prompt": "",
            "model": "openai/gpt-4o-mini",
            "model_source": "local",
            "tools": [],
            "runtime_keys": ["intent_router", "router"],
            "supports_prompt_edit": False,
            "supports_tools_edit": False,
        },
    }

    # Aplica overrides persistidos (customizaÃ§Ãµes salvas pelo admin)
    _apply_overrides()
    _apply_supabase_model_overrides()
    _initialized = True
    logger.info(f"[REGISTRY] Inicializado com {len(_REGISTRY)} agentes")


def _ensure_initialized():
    """Garante que o registry foi inicializado antes de qualquer leitura."""
    if not _initialized:
        initialize()


def _apply_overrides():
    """
    LÃª configs_override.json e sobrescreve os valores padrÃ£o com as
    customizaÃ§Ãµes salvas pelo admin. Falha silenciosamente se o arquivo
    nÃ£o existir ou estiver corrompido.
    """
    if not _OVERRIDE_FILE.exists():
        return
    try:
        overrides = json.loads(_OVERRIDE_FILE.read_text(encoding="utf-8"))
        for agent_id, data in overrides.items():
            if agent_id in _REGISTRY:
                _REGISTRY[agent_id].update(data)
        logger.info(f"[REGISTRY] Overrides aplicados: {list(overrides.keys())}")
    except Exception as e:
        logger.warning(f"[REGISTRY] Falha ao carregar overrides: {e}")


def _save_overrides():
    """
    Persiste o estado atual de todos os agentes em configs_override.json.
    Chamado sempre que update_agent() Ã© usado, garantindo que mudanÃ§as
    sobrevivam ao restart do servidor.

    Nota: o model e o prompt tambÃ©m sÃ£o escritos nos arquivos .py
    pelo admin.py via regex/AST. Este JSON serve de backup em memÃ³ria.
    """
    try:
        overrides = {
            agent_id: {
                "system_prompt": agent["system_prompt"],
                "model": agent["model"],
                "tools": agent["tools"],
            }
            for agent_id, agent in _REGISTRY.items()
        }
        _OVERRIDE_FILE.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.error(f"[REGISTRY] Falha ao salvar overrides: {e}")


def _apply_supabase_model_overrides():
    """
    Modelos dos agentes são carregados do Supabase e sobrepõem qualquer valor
    vindo do JSON local. Em caso de falha, o registry continua com fallback local.
    """
    try:
        from backend.services.agent_model_overrides import list_agent_model_overrides

        overrides = list_agent_model_overrides()
        applied: list[str] = []
        for agent_id, model in overrides.items():
            if agent_id not in _REGISTRY:
                continue
            _REGISTRY[agent_id]["model"] = model
            _REGISTRY[agent_id]["model_source"] = "supabase"
            applied.append(agent_id)

        if applied:
            logger.info(f"[REGISTRY] Modelos carregados do Supabase: {applied}")
    except Exception as e:
        logger.warning(f"[REGISTRY] Falha ao carregar modelos do Supabase: {e}")


# â”€â”€ API PÃºblica â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FunÃ§Ãµes usadas pelo orchestrator.py e pelos endpoints de admin.

def get_all() -> list[dict]:
    """Retorna lista com a configuraÃ§Ã£o atual de todos os agentes."""
    _ensure_initialized()
    return list(_REGISTRY.values())


def get_agent(agent_id: str) -> dict | None:
    """Retorna a configuraÃ§Ã£o de um agente especÃ­fico, ou None se nÃ£o existir."""
    _ensure_initialized()
    return _REGISTRY.get(agent_id)


def get_prompt(agent_id: str) -> str:
    """Retorna o system prompt atual do agente (padrÃ£o ou customizado pelo admin)."""
    _ensure_initialized()
    agent = _REGISTRY.get(agent_id)
    return agent["system_prompt"] if agent else ""


def get_model(agent_id: str) -> str:
    """
    Retorna o modelo configurado para o agente.
    Fallback para o modelo padrÃ£o do .env se nÃ£o houver override.
    """
    _ensure_initialized()
    agent = _REGISTRY.get(agent_id)
    if agent and agent.get("model"):
        return agent["model"]
    from backend.core.config import get_config
    return get_config().openrouter_model


def get_tools(agent_id: str) -> list:
    """Retorna a lista de tools do agente (formato OpenRouter/OpenAI)."""
    _ensure_initialized()
    agent = _REGISTRY.get(agent_id)
    return agent.get("tools", []) if agent else []


def update_agent(agent_id: str, data: dict) -> bool:
    """
    Atualiza campos de um agente em memÃ³ria e persiste no JSON override.

    Nota: este mÃ©todo NÃƒO reescreve os arquivos .py â€” isso Ã© feito
    separadamente pelo admin.py antes de chamar este mÃ©todo.

    Retorna False se o agent_id nÃ£o existir.
    """
    _ensure_initialized()
    if agent_id not in _REGISTRY:
        return False
    _REGISTRY[agent_id].update(data)
    _save_overrides()
    logger.info(f"[REGISTRY] Agente '{agent_id}' atualizado e persistido")
    return True


def reload_models_from_supabase() -> list[dict]:
    """
    Reaplica os modelos do Supabase no registry atual.
    Mantém prompts e tools locais intactos e retorna a lista atualizada.
    """
    _ensure_initialized()
    for agent in _REGISTRY.values():
        agent["model_source"] = "local"
    _apply_supabase_model_overrides()
    return get_all()
