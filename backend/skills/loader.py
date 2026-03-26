"""
Loader de Skills Dinâmicas — Arcco AI

Responsabilidades:
  1. Descoberta automática: escaneia backend/skills/ e carrega todos os módulos
     que expõem SKILL_META + execute().
  2. Geração de tool definitions: converte SKILL_META → formato OpenAI function calling.
  3. Execução: despacha chamadas do orquestrador para o execute() correto.

Uso no orchestrator.py:
    from backend.skills import loader as skills_loader

    # Injeta tools do supervisor
    active_tools += skills_loader.get_skill_tool_definitions()

    # Verifica se uma tool_call é uma skill
    if skills_loader.is_skill(func_name):
        result = await skills_loader.execute_dynamic_skill(func_name, func_args)

Uso no planner.py:
    _skill_defs = skills_loader.get_skill_tool_definitions()
    # Injeta descrições no system prompt do planner
"""

import importlib
import logging
import pkgutil
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

# Cache interno: skill_id → módulo Python
_SKILLS: dict[str, ModuleType] = {}
_LOADED = False

# Módulos que não são skills
_SKIP_MODULES = {"base", "loader"}


def _discover() -> None:
    """Escaneia o diretório skills/ e carrega todos os módulos válidos."""
    global _LOADED
    if _LOADED:
        return

    skills_dir = Path(__file__).parent
    loaded = []
    errors = []

    for finder, module_name, _ispkg in pkgutil.iter_modules([str(skills_dir)]):
        if module_name in _SKIP_MODULES:
            continue

        full_module = f"backend.skills.{module_name}"
        try:
            mod = importlib.import_module(full_module)
        except Exception as e:
            errors.append(f"{module_name}: {e}")
            logger.warning(f"[SKILLS] Falha ao importar skill '{module_name}': {e}")
            continue

        meta = getattr(mod, "SKILL_META", None)
        execute_fn = getattr(mod, "execute", None)

        if meta is None or execute_fn is None:
            logger.debug(f"[SKILLS] '{module_name}' ignorado — sem SKILL_META ou execute()")
            continue

        skill_id = meta.get("id")
        if not skill_id:
            logger.warning(f"[SKILLS] '{module_name}' ignorado — SKILL_META sem 'id'")
            continue

        _SKILLS[skill_id] = mod
        loaded.append(skill_id)

    _LOADED = True

    if loaded:
        logger.info(f"[SKILLS] {len(loaded)} skill(s) carregada(s): {loaded}")
    else:
        logger.info("[SKILLS] Nenhuma skill encontrada em backend/skills/")

    if errors:
        logger.warning(f"[SKILLS] {len(errors)} erro(s) de importação: {errors}")


def reload() -> None:
    """Força redescoberta de todas as skills (útil em dev com --reload)."""
    global _LOADED
    _SKILLS.clear()
    _LOADED = False
    _discover()


def _skill_matches_intent(meta: dict, intent_lower: str) -> bool:
    """
    Verifica se uma skill é relevante para a intenção do usuário.

    Regras:
    - Se keywords estiver vazia ou ausente → sempre relevante (skill universal)
    - Se keywords tiver valores → relevante se qualquer keyword aparecer no intent
    """
    keywords = meta.get("keywords", [])
    if not keywords:
        return True  # skill universal: sempre injetada
    return any(kw.lower() in intent_lower for kw in keywords)


def get_skill_tool_definitions(user_intent: str = "") -> list[dict]:
    """
    Retorna tool definitions relevantes para a intenção do usuário.

    - Se user_intent for vazio: retorna todas as skills (compatibilidade)
    - Se user_intent for fornecido: filtra por keywords do SKILL_META
    - Skills sem keywords são sempre incluídas (skills universais)
    """
    _discover()
    intent_lower = user_intent.lower()
    tools = []
    for mod in _SKILLS.values():
        meta = mod.SKILL_META
        if not user_intent or _skill_matches_intent(meta, intent_lower):
            tools.append({
                "type": "function",
                "function": {
                    "name": meta["id"],
                    "description": meta["description"],
                    "parameters": meta["parameters"],
                },
            })
    if tools:
        logger.debug("[SKILLS] %d skill(s) relevante(s) para o intent fornecido.", len(tools))
    return tools


def is_skill(name: str) -> bool:
    """Retorna True se o nome corresponde a uma skill carregada."""
    _discover()
    return name in _SKILLS


def get_skill_ids() -> list[str]:
    """Retorna lista de todos os IDs de skills carregadas."""
    _discover()
    return list(_SKILLS.keys())


def get_skill_descriptions(user_intent: str = "") -> str:
    """
    Retorna string formatada para injeção no system prompt do planner.
    Filtra por relevância se user_intent for fornecido.
    Formato: '- skill_id: descrição'
    Retorna string vazia se não houver skills relevantes.
    """
    _discover()
    intent_lower = user_intent.lower()
    lines = []
    for mod in _SKILLS.values():
        meta = mod.SKILL_META
        if not user_intent or _skill_matches_intent(meta, intent_lower):
            lines.append(f"- {meta['id']}: {meta['description']}")
    return "\n".join(lines)


async def execute_dynamic_skill(skill_id: str, args: dict) -> str:
    """
    Executa uma skill pelo seu ID.

    Args:
        skill_id: ID da skill (ex: 'consultar_cnpj')
        args: Argumentos da tool call (dict já parseado do JSON)

    Returns:
        Resultado como string (será adicionado ao accumulated_context)

    Raises:
        ValueError: se a skill não existir
        Exception: propagado do execute() da skill
    """
    _discover()

    if skill_id not in _SKILLS:
        raise ValueError(
            f"Skill '{skill_id}' não encontrada. "
            f"Skills disponíveis: {list(_SKILLS.keys())}"
        )

    mod = _SKILLS[skill_id]
    execute_fn = mod.execute

    logger.debug(f"[SKILLS] Executando skill '{skill_id}' com args: {list(args.keys())}")
    result = await execute_fn(args)

    if not isinstance(result, str):
        result = str(result)

    logger.debug(f"[SKILLS] Skill '{skill_id}' retornou {len(result)} chars")
    return result
