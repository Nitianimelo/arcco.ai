"""
Cache de capacidades de modelos — aprendido em runtime.

Quando um modelo falha por limitação conhecida (ex: não suporta tool_choice forçado),
registra aqui. Na próxima requisição com o mesmo modelo, o sistema já sabe o caminho
correto e vai direto, sem tentar e falhar primeiro.

O cache vive enquanto o processo estiver rodando (memória). Num restart limpo,
o sistema aprende de novo nas primeiras chamadas. Isso é intencional: modelos
atualizam seus endpoints no OpenRouter e podem ganhar capacidades novas.
"""

import logging

logger = logging.getLogger(__name__)

# ── Conjuntos de modelos com limitações conhecidas ────────────────────────────

# Modelos que rejeitaram tool_choice forçado (404 OpenRouter)
# Nesses modelos, sempre usamos tool_choice="auto" + instrução textual
_NO_FORCED_TOOL_CHOICE: set[str] = set()

# Modelos que rejeitaram function calling completamente
# Nesses modelos, não passamos tools e usamos parsing textual
_NO_TOOLS: set[str] = set()

# ── API Pública ───────────────────────────────────────────────────────────────

def supports_forced_tool_choice(model: str) -> bool:
    """True se o modelo aceita tool_choice forçado (ex: {'type': 'function', ...})."""
    return model not in _NO_FORCED_TOOL_CHOICE


def mark_no_forced_tool_choice(model: str) -> None:
    """Registra que o modelo não suporta tool_choice forçado."""
    if model not in _NO_FORCED_TOOL_CHOICE:
        _NO_FORCED_TOOL_CHOICE.add(model)
        logger.info(
            "[MODEL_CAP] '%s' registrado como sem suporte a tool_choice forçado. "
            "Próximas chamadas usarão tool_choice='auto' diretamente.",
            model,
        )


def supports_tools(model: str) -> bool:
    """True se o modelo aceita function calling."""
    return model not in _NO_TOOLS


def mark_no_tools(model: str) -> None:
    """Registra que o modelo não suporta function calling."""
    if model not in _NO_TOOLS:
        _NO_TOOLS.add(model)
        logger.warning(
            "[MODEL_CAP] '%s' registrado como sem suporte a function calling. "
            "Considere trocar o modelo do agente 'chat' no painel admin.",
            model,
        )


def get_summary() -> dict:
    """Retorna resumo das capacidades aprendidas (útil para debug/admin)."""
    return {
        "no_forced_tool_choice": sorted(_NO_FORCED_TOOL_CHOICE),
        "no_tools": sorted(_NO_TOOLS),
    }
