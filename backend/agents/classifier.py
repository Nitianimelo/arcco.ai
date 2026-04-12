"""
Classificador leve de intent — substitui o planner na nova arquitetura.

Objetivo:
- Classificar o task_type a partir do intent do usuário.
- Gerar hints operacionais para o Supervisor (sem steps determinísticos).
- Detectar ambiguidades e gerar perguntas de clarificação visual.
- Usar modelo econômico (gpt-4o-mini via registry "classifier").
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from backend.agents import registry
from backend.agents.contracts import (
    ClassifierOutputContract,
    ClarificationOptionContract,
    ClarificationQuestionContract,
)
from backend.agents.task_types import get_task_type_catalog, infer_task_type

logger = logging.getLogger(__name__)

_CLASSIFIER_TIMEOUT_SECONDS = 20.0
_CLASSIFIER_FALLBACK_MODEL = "openai/gpt-4o-mini"
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


# ---------------------------------------------------------------------------
# Clarificação visual — questions pré-definidas por tipo de ambiguidade
# ---------------------------------------------------------------------------

_DESIGN_STYLE_QUESTION = ClarificationQuestionContract(
    type="choice",
    text="Qual estilo visual você prefere?",
    options=["Minimalista", "Corporativo", "Ousado/Moderno", "Elegante"],
    option_details=[
        ClarificationOptionContract(
            label="Minimalista",
            description="Cores neutras, muito branco, tipografia clean",
            recommended=True,
        ),
        ClarificationOptionContract(
            label="Corporativo",
            description="Profissional, cores sóbrias, estruturado",
        ),
        ClarificationOptionContract(
            label="Ousado/Moderno",
            description="Cores vibrantes, layout assimétrico, impacto visual",
        ),
        ClarificationOptionContract(
            label="Elegante",
            description="Tons escuros, serif, sofisticado",
        ),
    ],
    helper_text="Escolha o estilo que mais combina com o resultado que você espera.",
)

_DOCUMENT_FORMAT_QUESTION = ClarificationQuestionContract(
    type="choice",
    text="Qual formato de entrega você prefere?",
    options=["Documento de texto (PDF/DOCX)", "Apresentação (slides)", "Planilha (Excel/CSV)", "Texto direto no chat"],
    option_details=[
        ClarificationOptionContract(
            label="Documento de texto (PDF/DOCX)",
            description="Relatório ou documento formatado para download",
            recommended=True,
        ),
        ClarificationOptionContract(
            label="Apresentação (slides)",
            description="Deck visual com slides para apresentar",
        ),
        ClarificationOptionContract(
            label="Planilha (Excel/CSV)",
            description="Dados organizados em tabela para análise",
        ),
        ClarificationOptionContract(
            label="Texto direto no chat",
            description="Resposta textual simples sem arquivo",
        ),
    ],
    helper_text="Isso me ajuda a escolher a melhor rota de geração.",
)

_FILE_ACTION_QUESTION = ClarificationQuestionContract(
    type="choice",
    text="O que você quer que eu faça com o arquivo?",
    options=["Resumir o conteúdo", "Extrair dados específicos", "Redesenhar/reformatar", "Analisar e comentar"],
    option_details=[
        ClarificationOptionContract(
            label="Resumir o conteúdo",
            description="Gerar um resumo textual do documento",
        ),
        ClarificationOptionContract(
            label="Extrair dados específicos",
            description="Puxar tabelas, nomes, valores ou seções",
        ),
        ClarificationOptionContract(
            label="Redesenhar/reformatar",
            description="Criar nova versão visual ou reorganizar",
        ),
        ClarificationOptionContract(
            label="Analisar e comentar",
            description="Revisar conteúdo e dar feedback",
            recommended=True,
        ),
    ],
    helper_text="Cada opção usa uma rota diferente de processamento.",
)

_SEARCH_SCOPE_QUESTION = ClarificationQuestionContract(
    type="choice",
    text="Qual nível de profundidade você precisa?",
    options=["Busca rápida (top 5)", "Pesquisa moderada (10-20 resultados)", "Pesquisa profunda (análise completa)"],
    option_details=[
        ClarificationOptionContract(
            label="Busca rápida (top 5)",
            description="Resultados imediatos, foco em velocidade",
            recommended=True,
        ),
        ClarificationOptionContract(
            label="Pesquisa moderada (10-20 resultados)",
            description="Cobertura razoável com verificação de fontes",
        ),
        ClarificationOptionContract(
            label="Pesquisa profunda (análise completa)",
            description="Pesquisa extensa com múltiplas fontes e síntese",
        ),
    ],
    helper_text="Pesquisas mais profundas levam mais tempo mas trazem dados mais confiáveis.",
)


# ---------------------------------------------------------------------------
# Detecção de ambiguidade por task_type
# ---------------------------------------------------------------------------

_DESIGN_VAGUE_PATTERNS = re.compile(
    r"\b(design|capa|banner|poster|slide|apresenta|visual|layout)\b",
    re.IGNORECASE,
)
_DESIGN_HAS_STYLE = re.compile(
    r"\b(minimalista|corporativo|ousado|moderno|elegante|clean|dark|claro|escuro|colorido|neutro|sóbrio|sobrio)\b",
    re.IGNORECASE,
)

_FILE_VAGUE_PATTERNS = re.compile(
    r"\b(pdf|arquivo|anexo|documento|docx|xlsx)\b",
    re.IGNORECASE,
)
_FILE_HAS_ACTION = re.compile(
    r"\b(resum|extra|redesenh|reform|analise|analis|convert|transfor|reorgani)\b",
    re.IGNORECASE,
)


def _detect_ambiguity(
    user_intent: str,
    task_type: str,
    has_session_files: bool,
) -> list[ClarificationQuestionContract]:
    """Detecta ambiguidades no intent e retorna questions visuais."""
    questions: list[ClarificationQuestionContract] = []
    normalized = (user_intent or "").strip()

    if task_type == "design_generation":
        if _DESIGN_VAGUE_PATTERNS.search(normalized) and not _DESIGN_HAS_STYLE.search(normalized):
            questions.append(_DESIGN_STYLE_QUESTION)

    elif task_type in ("document_generation", "deep_research"):
        # Documento genérico sem formato claro
        pass  # O Supervisor decide o formato; não bloquear

    elif task_type == "file_transformation" or (
        has_session_files
        and _FILE_VAGUE_PATTERNS.search(normalized)
        and not _FILE_HAS_ACTION.search(normalized)
    ):
        questions.append(_FILE_ACTION_QUESTION)

    return questions


# ---------------------------------------------------------------------------
# Geração de hints operacionais (sem LLM)
# ---------------------------------------------------------------------------

def _generate_hints(
    user_intent: str,
    task_type: str,
    session_file_names: list[str],
) -> list[str]:
    """Gera hints operacionais baseado no intent e inventário."""
    hints: list[str] = []
    normalized = (user_intent or "").lower()

    # Hint: ler anexos primeiro
    if session_file_names:
        file_mentioned = any(
            name.lower().split(".")[0] in normalized
            for name in session_file_names
            if name
        )
        if file_mentioned or task_type in ("file_transformation", "mass_document_analysis", "open_problem_solving"):
            hints.append(f"Ler anexos da sessão primeiro: {', '.join(session_file_names[:5])}")

    # Hint: busca web necessária
    if task_type in ("entity_collection", "spreadsheet_generation", "deep_research", "browser_workflow"):
        hints.append("Busca web necessária antes de gerar resultado")

    # Hint: design visual
    if task_type == "design_generation":
        hints.append("Gerar artefato visual HTML/CSS como entrega final")

    # Hint: documento textual
    if task_type == "document_generation":
        hints.append("Gerar documento textual como entrega final")

    # Hint: Instagram/visual
    instagram_tokens = ("instagram", "post", "carrossel", "story", "stories", "reels")
    if any(tok in normalized for tok in instagram_tokens):
        hints.append("Pedido visual para redes sociais — usar formato 1:1 ou 9:16")

    return hints


# ---------------------------------------------------------------------------
# LLM classification (opcional — fallback para infer_task_type)
# ---------------------------------------------------------------------------

def _extract_json_payload(raw_content: str) -> dict:
    """Extrai JSON do output do LLM."""
    cleaned = (raw_content or "").strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    candidates = [fenced]
    match = _JSON_BLOCK_RE.search(fenced)
    if match:
        candidates.append(match.group(0))
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Classifier retornou JSON inválido: {last_error}")


async def _call_llm_classifier(
    user_intent: str,
    session_file_names: list[str],
    model: str,
) -> ClassifierOutputContract | None:
    """Tenta classificar via LLM. Retorna None se falhar."""
    system_prompt = registry.get_prompt("classifier")
    if not system_prompt:
        return None

    catalog_summary = "\n".join(
        f"- {item['task_type']}: {item['description']}"
        for item in get_task_type_catalog()
    )

    files_context = ""
    if session_file_names:
        files_context = f"\nArquivos na sessão: {', '.join(session_file_names[:10])}"

    user_message = (
        f"Pedido do usuário: {user_intent}"
        f"{files_context}"
        f"\n\nTipos de tarefa disponíveis:\n{catalog_summary}"
        "\n\nRetorne APENAS o JSON com: task_type, hints[], acknowledgment."
        " Se o pedido for ambíguo, retorne needs_clarification=true."
    )

    try:
        from backend.core.llm import call_openrouter

        data = await asyncio.wait_for(
            call_openrouter(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                model=model,
                max_tokens=600,
                temperature=0.1,
            ),
            timeout=_CLASSIFIER_TIMEOUT_SECONDS,
        )
        raw = data["choices"][0]["message"]["content"].strip()
        parsed = _extract_json_payload(raw)
        return ClassifierOutputContract.model_validate(parsed)
    except Exception as exc:
        logger.warning("[CLASSIFIER] LLM classification failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

async def classify(
    *,
    user_intent: str,
    session_file_names: list[str] | None = None,
    use_llm: bool = True,
) -> ClassifierOutputContract:
    """
    Classifica o intent do usuário e retorna task_type + hints + clarification.

    Fluxo:
    1. Tenta LLM se use_llm=True (modelo do registry "classifier")
    2. Fallback: infer_task_type() + hints heurísticos
    3. Detecta ambiguidades → gera questions visuais
    """
    files = session_file_names or []
    has_files = bool(files)

    # Tenta LLM classification
    llm_result: ClassifierOutputContract | None = None
    if use_llm:
        model = registry.get_model("classifier") or _CLASSIFIER_FALLBACK_MODEL
        llm_result = await _call_llm_classifier(user_intent, files, model)

    # Resolve task_type
    if llm_result and llm_result.task_type != "general_request":
        task_type = llm_result.task_type
        logger.info("[CLASSIFIER] LLM task_type=%s", task_type)
    else:
        task_type = infer_task_type(user_intent)
        logger.info("[CLASSIFIER] Heuristic task_type=%s", task_type)

    # Gera hints (heurísticos — sempre roda, LLM hints são merge)
    hints = _generate_hints(user_intent, task_type, files)
    if llm_result and llm_result.hints:
        # Merge LLM hints com heurísticos (sem duplicar)
        existing = set(hints)
        for hint in llm_result.hints:
            if hint not in existing:
                hints.append(hint)

    # Detecta ambiguidades visuais
    ambiguity_questions = _detect_ambiguity(user_intent, task_type, has_files)

    # Merge com questions do LLM (se houver)
    all_questions = list(ambiguity_questions)
    if llm_result and llm_result.clarification_questions:
        all_questions.extend(llm_result.clarification_questions)

    needs_clarification = bool(all_questions) or (llm_result.needs_clarification if llm_result else False)

    acknowledgment = ""
    if llm_result and llm_result.acknowledgment:
        acknowledgment = llm_result.acknowledgment

    return ClassifierOutputContract(
        task_type=task_type,
        needs_clarification=needs_clarification,
        clarification_questions=all_questions,
        hints=hints,
        acknowledgment=acknowledgment,
    )
