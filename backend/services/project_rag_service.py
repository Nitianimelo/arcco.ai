"""
RAG baseado em pgvector (OpenAI text-embedding-3-small) para projetos persistentes.

search_project_context() — busca chunks por similaridade semântica via RPC pgvector
insert_chunks_for_file()  — divide texto em chunks, gera embeddings em batch e insere
"""

import logging

from backend.core.supabase_client import get_supabase_client
from backend.services.ephemeral_rag_service import chunk_text
from backend.services.embedding_service import get_embedding, get_embeddings_batch

logger = logging.getLogger(__name__)

_TABLE = "project_file_chunks"

# Tamanho do batch para geração de embeddings (OpenAI permite até 2048, mas usamos
# 100 para controlar rate limit e tamanho de payload)
_EMBED_BATCH_SIZE = 100

# Tamanho do batch para insert no Supabase
_INSERT_BATCH_SIZE = 50


def search_project_context(project_id: str, query: str, top_k: int = 5) -> str:
    """
    Busca chunks semanticamente relevantes via similaridade coseno com pgvector.
    Gera embedding da query e chama a função RPC search_project_chunks.
    Retorna string formatada com os chunks ou "" se sem resultado.
    """
    if not project_id or not query or not query.strip():
        return ""

    # Gera embedding da query (trunca a 500 chars — suficiente para capturar intenção)
    try:
        query_embedding = get_embedding(query.strip()[:500])
    except Exception as e:
        logger.error(f"[RAG] Falha ao gerar embedding da query: {e}")
        return ""

    db = get_supabase_client()
    try:
        rows = db.rpc(
            "search_project_chunks",
            {
                "p_project_id": project_id,
                "p_embedding": query_embedding,
                "p_top_k": top_k,
            },
        )
    except Exception as e:
        logger.error(f"[RAG] Falha na busca por similaridade semântica: {e}")
        return ""

    if not rows:
        return ""

    chunks = [row["chunk_text"] for row in rows if row.get("chunk_text")]
    if not chunks:
        return ""

    formatted = ["Contexto relevante da base de conhecimento do projeto:"]
    for i, chunk in enumerate(chunks, 1):
        formatted.append(f"\n[Trecho {i}]\n{chunk.strip()}")

    return "\n".join(formatted).strip()


def insert_chunks_for_file(
    project_file_id: str, project_id: str, extracted_text: str
) -> None:
    """
    Divide o texto extraído em chunks, gera embeddings em batch via OpenAI e
    insere na tabela project_file_chunks com os vetores.
    Chamado após extração bem-sucedida de um project_file.
    """
    if not extracted_text or not extracted_text.strip():
        logger.info(f"[RAG] Texto vazio para {project_file_id}, pulando indexação.")
        return

    db = get_supabase_client()

    # Remove chunks antigos deste arquivo (re-indexação limpa)
    try:
        db.delete(_TABLE, {"project_file_id": project_file_id})
    except Exception as e:
        logger.warning(f"[RAG] Falha ao limpar chunks antigos de {project_file_id}: {e}")

    chunks = chunk_text(extracted_text)
    if not chunks:
        return

    # Gera embeddings em batches para não estourar rate limit da OpenAI
    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch_texts = chunks[i : i + _EMBED_BATCH_SIZE]
        try:
            embeddings = get_embeddings_batch(batch_texts)
            all_embeddings.extend(embeddings)
        except Exception as e:
            logger.error(
                f"[RAG] Falha ao gerar embeddings (batch {i // _EMBED_BATCH_SIZE}): {e}"
            )
            raise  # Re-raise para marcar o arquivo como failed no project_file_service

    # Monta rows com embedding incluído
    rows = [
        {
            "project_file_id": project_file_id,
            "project_id": project_id,
            "chunk_text": chunk,
            "embedding": embedding,
            "chunk_index": idx,
        }
        for idx, (chunk, embedding) in enumerate(zip(chunks, all_embeddings))
    ]

    # Insert em batches para evitar payload gigante
    total_inserted = 0
    for i in range(0, len(rows), _INSERT_BATCH_SIZE):
        batch = rows[i : i + _INSERT_BATCH_SIZE]
        try:
            db.insert_many(_TABLE, batch)
            total_inserted += len(batch)
        except Exception as e:
            logger.error(f"[RAG] Falha ao inserir batch {i // _INSERT_BATCH_SIZE}: {e}")
            raise

    logger.info(
        f"[RAG] {total_inserted}/{len(rows)} chunks com embeddings indexados "
        f"para arquivo {project_file_id}."
    )
