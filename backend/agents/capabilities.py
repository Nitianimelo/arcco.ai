"""
Catálogo canônico de capabilities do backend.

Objetivo:
- Dar uma fonte de verdade estável para IA e humanos.
- Separar agent/tool/skill/capability para reduzir ambiguidade.
- Servir como base de metadata para logs e futuras refatorações.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


CapabilityKind = Literal["tool", "specialist", "skill", "system"]
OutputType = Literal[
    "text",
    "search_result",
    "browser_result",
    "python_result",
    "session_file_result",
    "file_artifact",
    "design_artifact",
    "research_report",
    "skill_result",
    "control",
]


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    display_name: str
    kind: CapabilityKind
    route: str
    tool_name: str | None
    owning_agent: str
    is_terminal: bool
    requires_guardrails: bool
    supports_handoff: bool
    output_type: OutputType
    allowed_in_planner: bool = True
    allowed_in_react: bool = True
    notes: str = ""


ARCHITECTURE_VERSION = "capabilities-v2"


_CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="session_file_read",
        display_name="Leitura de Arquivo da Sessao",
        kind="tool",
        route="session_file",
        tool_name="read_session_file",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="session_file_result",
        notes="Le o texto extraido de anexos da sessao atual.",
    ),
    CapabilityDefinition(
        capability_id="text_document_generate",
        display_name="Geracao de Documento de Texto",
        kind="specialist",
        route="text_generator",
        tool_name="ask_text_generator",
        owning_agent="text_generator",
        is_terminal=True,
        requires_guardrails=True,
        supports_handoff=False,
        output_type="file_artifact",
        notes="Especialista terminal para documentos textuais.",
    ),
    CapabilityDefinition(
        capability_id="design_generate",
        display_name="Geracao de Design",
        kind="specialist",
        route="design_generator",
        tool_name="ask_design_generator",
        owning_agent="design_generator",
        is_terminal=True,
        requires_guardrails=True,
        supports_handoff=False,
        output_type="design_artifact",
        notes="Especialista terminal para HTML visual.",
    ),
    CapabilityDefinition(
        capability_id="file_modify",
        display_name="Modificacao de Arquivo",
        kind="specialist",
        route="file_modifier",
        tool_name="ask_file_modifier",
        owning_agent="file_modifier",
        is_terminal=False,
        requires_guardrails=True,
        supports_handoff=False,
        output_type="file_artifact",
        notes="Retorna URL de arquivo modificado; hoje o supervisor ainda consolida a resposta final.",
    ),
    CapabilityDefinition(
        capability_id="web_browse",
        display_name="Navegacao Web",
        kind="tool",
        route="browser",
        tool_name="ask_browser",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=True,
        output_type="browser_result",
        notes="Suporta pausa e retomada com handoff humano.",
    ),
    CapabilityDefinition(
        capability_id="web_search",
        display_name="Busca Web",
        kind="tool",
        route="web_search",
        tool_name="ask_web_search",
        owning_agent="web_researcher",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="search_result",
    ),
    CapabilityDefinition(
        capability_id="python_execute",
        display_name="Execucao Python",
        kind="tool",
        route="python",
        tool_name="execute_python",
        owning_agent="code_creator",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="python_result",
    ),
    CapabilityDefinition(
        capability_id="deep_research",
        display_name="Pesquisa Profunda",
        kind="specialist",
        route="deep_research",
        tool_name="deep_research",
        owning_agent="deep_research",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="research_report",
    ),
    CapabilityDefinition(
        capability_id="spy_pages",
        display_name="Spy Pages",
        kind="tool",
        route="spy_pages",
        tool_name="analyze_web_pages",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="skill_result",
    ),
    CapabilityDefinition(
        capability_id="skill_slide_generator",
        display_name="Skill Slide Generator",
        kind="skill",
        route="dynamic_skill",
        tool_name="slide_generator",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="skill_result",
        notes="Skill preparatoria para decks/carrosseis.",
    ),
    CapabilityDefinition(
        capability_id="skill_static_design_generator",
        display_name="Skill Static Design Generator",
        kind="skill",
        route="dynamic_skill",
        tool_name="static_design_generator",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="skill_result",
        notes="Pode virar artefato terminal por renderizacao local no orquestrador atual.",
    ),
    CapabilityDefinition(
        capability_id="skill_multi_doc_investigator",
        display_name="Skill Multi Doc Investigator",
        kind="skill",
        route="dynamic_skill",
        tool_name="multi_doc_investigator",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="skill_result",
    ),
    CapabilityDefinition(
        capability_id="skill_web_form_operator",
        display_name="Skill Web Form Operator",
        kind="skill",
        route="dynamic_skill",
        tool_name="web_form_operator",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=True,
        output_type="skill_result",
    ),
    CapabilityDefinition(
        capability_id="skill_local_lead_extractor",
        display_name="Skill Local Lead Extractor",
        kind="skill",
        route="dynamic_skill",
        tool_name="local_lead_extractor",
        owning_agent="chat",
        is_terminal=False,
        requires_guardrails=False,
        supports_handoff=False,
        output_type="skill_result",
    ),
)

_DIRECT_DISPATCH_ROUTES = frozenset({"session_file", "web_search", "python", "browser", "deep_research", "dynamic_skill"})
_TERMINAL_SPECIALIST_ROUTES = frozenset({"text_generator", "design_generator"})
_GUARDED_SPECIALIST_ROUTES = frozenset({"file_modifier"})
_LINK_ONLY_ROUTES = frozenset({"file_modifier"})
_LOCAL_RENDER_ROUTES = frozenset({"design_generator"})
_LOCAL_RENDER_TOOL_NAMES = frozenset({"static_design_generator"})
_ARTIFACT_TERMINAL_TOOL_NAMES = frozenset({"static_design_generator"})


def get_capability_catalog() -> list[dict]:
    return [asdict(item) for item in _CAPABILITIES]


def get_capability_summary() -> dict[str, object]:
    return {
        "architecture_version": ARCHITECTURE_VERSION,
        "total_capabilities": len(_CAPABILITIES),
        "terminal_capabilities": sorted(item.capability_id for item in _CAPABILITIES if item.is_terminal),
        "handoff_capabilities": sorted(item.capability_id for item in _CAPABILITIES if item.supports_handoff),
        "routes": sorted({item.route for item in _CAPABILITIES}),
        "kinds": sorted({item.kind for item in _CAPABILITIES}),
    }


def get_capability_by_tool_name(tool_name: str | None) -> dict | None:
    if not tool_name:
        return None
    for item in _CAPABILITIES:
        if item.tool_name == tool_name:
            return asdict(item)
    return None


def get_capability_by_route(route: str | None) -> dict | None:
    if not route:
        return None
    for item in _CAPABILITIES:
        if item.route == route:
            return asdict(item)
    return None


def get_direct_dispatch_routes() -> frozenset[str]:
    return _DIRECT_DISPATCH_ROUTES


def route_requires_link_only(route: str) -> bool:
    return route in _LINK_ONLY_ROUTES


def get_runtime_semantics(
    *,
    tool_name: str | None = None,
    route: str | None = None,
    planner_terminal: bool | None = None,
) -> dict[str, object]:
    normalized_route = route or ""
    normalized_tool_name = tool_name or ""

    execution_mode = "guarded_specialist"
    if normalized_route in _DIRECT_DISPATCH_ROUTES:
        execution_mode = "direct_dispatch"
    elif normalized_route in _TERMINAL_SPECIALIST_ROUTES:
        execution_mode = "terminal_specialist"

    if normalized_route in _TERMINAL_SPECIALIST_ROUTES:
        effective_terminal = True if planner_terminal is None else bool(planner_terminal)
    else:
        effective_terminal = False

    return {
        "execution_mode": execution_mode,
        "agent_role": "specialist" if normalized_route in (_TERMINAL_SPECIALIST_ROUTES | _GUARDED_SPECIALIST_ROUTES) else "tool",
        "direct_dispatch": normalized_route in _DIRECT_DISPATCH_ROUTES,
        "runs_with_guardrails": normalized_route in _GUARDED_SPECIALIST_ROUTES,
        "emit_links_only": normalized_route in _LINK_ONLY_ROUTES,
        "supports_local_design_render": (
            normalized_route in _LOCAL_RENDER_ROUTES
            or normalized_tool_name in _LOCAL_RENDER_TOOL_NAMES
        ),
        "artifact_terminal": normalized_tool_name in _ARTIFACT_TERMINAL_TOOL_NAMES,
        "terminal_specialist": normalized_route in _TERMINAL_SPECIALIST_ROUTES,
        "effective_terminal": effective_terminal,
    }
