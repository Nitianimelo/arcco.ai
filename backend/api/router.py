"""
Endpoint de roteamento de intent.
Portado de netlify/functions/agent-router.ts
"""

import re
import logging

from fastapi import APIRouter

from backend.models.schemas import RouteRequest, RouteResponse
from backend.core.llm import call_openrouter

logger = logging.getLogger(__name__)
router = APIRouter()

# Padrões de keywords para classificação zero-token
KEYWORD_PATTERNS = {
    "web_search": re.compile(
        r"\b(pesquis|busc|procur|encontr|search|google|internet|quem é|o que é)\w*",
        re.IGNORECASE,
    ),
    "ocr_scan": re.compile(
        r"\b(leia|ler|extrair|texto da imagem|scan|ocr)\w*",
        re.IGNORECASE,
    ),
    "generate_file": re.compile(
        r"\b(gera|cri)\w*\s+(pdf|documento|relatório|report|slide|apresentação|pptx|planilha|excel|xlsx|word|docx)",
        re.IGNORECASE,
    ),
    "deep_search": re.compile(
        r"\b(pesquisa profunda|deep search|relatório completo|investiga)\w*",
        re.IGNORECASE,
    ),
}


def match_keywords(message: str) -> str | None:
    """Classificação por keywords (zero tokens)."""
    for intent, pattern in KEYWORD_PATTERNS.items():
        if pattern.search(message):
            return intent
    return None


async def classify_with_llm(message: str) -> str:
    """Classificação por LLM (fallback)."""
    try:
        data = await call_openrouter(
            messages=[{
                "role": "user",
                "content": (
                    'Classify intent: web_search, generate_file, ocr_scan, '
                    'deep_search, general_chat.\n'
                    f'Message: "{message}"\n'
                    'Return ONLY the intent.'
                ),
            }],
            max_tokens=20,
        )
        result = data["choices"][0]["message"]["content"]
        return result.strip().lower()
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return "general_chat"


@router.post("/route", response_model=RouteResponse)
async def route_endpoint(req: RouteRequest):
    """
    Classifica a intenção da mensagem.
    1. Tenta keywords (zero tokens)
    2. Fallback para LLM
    """
    if not req.message or not req.user_id:
        return RouteResponse(type="error", error="Missing message or user_id")

    # 1. Keyword matching
    intent = match_keywords(req.message)
    confidence = 1.0 if intent else 0.0

    # 2. LLM fallback
    if not intent:
        intent = await classify_with_llm(req.message)
        confidence = 0.8

    # 3. Retornar
    if intent in ("web_search", "generate_file", "ocr_scan"):
        return RouteResponse(
            type="action",
            intent=intent,
            confidence=confidence,
            payload={"message": req.message},
        )

    return RouteResponse(
        type="reasoning",
        intent=intent or "general_chat",
        confidence=confidence,
    )
