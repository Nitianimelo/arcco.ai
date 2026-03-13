"""
RAG lexical efêmero para arquivos de sessão.

V1:
- chunking com overlap
- ranqueamento simples por frequência de termos da query
- sem embeddings, sem índice persistente
"""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TOP_K = 5
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    clean_text = (text or "").strip()
    if not clean_text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser maior que zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap deve ser >= 0 e menor que chunk_size.")

    chunks: list[str] = []
    start = 0
    text_length = len(clean_text)
    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunks.append(clean_text[start:end].strip())
        if end == text_length:
            break
        start = max(0, end - overlap)
    return [chunk for chunk in chunks if chunk]


def normalize_query(query: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(query or "")]


def score_chunk(chunk: str, terms: list[str]) -> int:
    if not chunk or not terms:
        return 0

    chunk_terms = [match.group(0).lower() for match in TOKEN_RE.finditer(chunk)]
    frequencies = Counter(chunk_terms)
    unique_terms = set(terms)
    return sum(frequencies.get(term, 0) for term in unique_terms)


def search_relevant_chunks(
    text: str,
    query: str,
    limit: int = DEFAULT_TOP_K,
) -> list[str]:
    chunks = chunk_text(text)
    terms = normalize_query(query)
    if not chunks:
        return []

    if not terms:
        return chunks[:limit]

    scored_chunks: list[tuple[int, int, str]] = []
    for index, chunk in enumerate(chunks):
        score = score_chunk(chunk, terms)
        if score > 0:
            scored_chunks.append((score, index, chunk))

    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    results = [chunk for _, _, chunk in scored_chunks[:limit]]
    logger.info(
        "Busca lexical retornou %s chunk(s) relevantes para query '%s'",
        len(results),
        query[:120],
    )
    return results


def format_chunk_results(file_name: str, chunks: list[str]) -> str:
    if not chunks:
        return f"Nenhum trecho relevante encontrado em '{file_name}'."

    formatted = [f"Trechos relevantes encontrados em '{file_name}':"]
    for index, chunk in enumerate(chunks, start=1):
        formatted.append(f"\n[Chunk {index}]\n{chunk.strip()}")
    return "\n".join(formatted).strip()
