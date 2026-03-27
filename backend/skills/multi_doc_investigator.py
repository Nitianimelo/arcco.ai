"""
Skill: Multi-Document Investigator

Permite fazer perguntas complexas sobre dezenas de documentos
anexados na sessao atual. Usa o RAG Efemero lexical para encontrar
os trechos mais relevantes e sintetiza um dossie citando fontes.

Fluxo:
  1. Lista todos os arquivos da sessao
  2. Para cada arquivo processado, busca chunks relevantes via RAG lexical
  3. Envia chunks + query ao LLM para sintese com citacao de fontes
"""

import logging
from pathlib import Path

from backend.core.llm import call_openrouter
from backend.agents import registry

logger = logging.getLogger(__name__)

# ── Contrato da Skill ─────────────────────────────────────────────────────────

SKILL_META = {
    "id": "multi_doc_investigator",
    "name": "Investigador Multi-Documento",
    "description": (
        "Responde perguntas complexas cruzando informacoes de TODOS os documentos "
        "anexados na sessao atual. Cita de qual arquivo cada informacao foi retirada. "
        "Use quando o usuario tem multiplos documentos (PDFs, planilhas, contratos) "
        "e quer encontrar dados especificos, comparar informacoes entre documentos, "
        "ou gerar um relatorio consolidado a partir de varias fontes."
    ),
    "keywords": [
        "documentos", "arquivos", "comparar", "cruzar", "investigar",
        "analisar documentos", "todos os arquivos", "dossie", "dossiê",
        "contrato", "contratos", "relatorio", "relatório",
        "buscar nos documentos", "encontrar nos arquivos",
        "multiplos", "múltiplos", "consolidar",
    ],
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "ID da sessao atual (passado automaticamente pelo orquestrador)",
            },
            "investigation_query": {
                "type": "string",
                "description": (
                    "A pergunta ou instrucao do usuario sobre os documentos. "
                    "Ex: 'Qual o valor total de todos os contratos?', "
                    "'Compare as clausulas de rescisao entre os documentos'"
                ),
            },
        },
        "required": ["session_id", "investigation_query"],
    },
}

# Quantos chunks buscar por arquivo
_CHUNKS_PER_FILE = 5
# Maximo de chunks totais para enviar ao LLM (evita estourar contexto)
_MAX_TOTAL_CHUNKS = 30
# Maximo de caracteres de contexto para o LLM
_MAX_CONTEXT_CHARS = 25000


# ── Execucao ───────────────────────────────────────────────────────────────────

async def execute(args: dict) -> str:
    """
    Investiga multiplos documentos da sessao para responder uma query.

    Args:
        args["session_id"]: ID da sessao com os documentos
        args["investigation_query"]: pergunta do usuario

    Returns:
        Dossie formatado com citacoes de fonte
    """
    import asyncio

    session_id = args.get("session_id", "").strip()
    query = args.get("investigation_query", "").strip()

    if not session_id:
        return "Erro: session_id nao informado. Esta skill precisa ser usada numa sessao com arquivos anexados."
    if not query:
        return "Erro: nenhuma pergunta foi fornecida. Informe o que deseja investigar nos documentos."

    logger.info("[INVESTIGATOR] Sessao %s, query: %s", session_id, query[:100])

    # ── Passo A: Listar e verificar arquivos da sessao ─────────────────────────
    try:
        from backend.services.session_file_service import (
            list_session_files,
            touch_session,
        )
        touch_session(session_id)
        files = list_session_files(session_id)
    except Exception as e:
        logger.error("[INVESTIGATOR] Falha ao listar arquivos: %s", e)
        return f"Erro ao acessar arquivos da sessao: {e}"

    if not files:
        return (
            "Nenhum arquivo encontrado nesta sessao. "
            "Faca upload de documentos primeiro e tente novamente."
        )

    # Filtra apenas arquivos ja processados (status "ready")
    ready_files = [f for f in files if f.get("status") == "ready"]
    processing = [f for f in files if f.get("status") in ("uploaded", "processing")]

    if not ready_files and processing:
        return (
            f"{len(processing)} arquivo(s) ainda estao sendo processados (OCR/extracao de texto). "
            "Aguarde alguns instantes e tente novamente."
        )
    if not ready_files:
        return "Nenhum arquivo processado encontrado na sessao. Verifique se os uploads foram concluidos."

    logger.info("[INVESTIGATOR] %d arquivos prontos de %d total", len(ready_files), len(files))

    # ── Passo B: Busca RAG lexical em cada arquivo ─────────────────────────────
    from backend.services.ephemeral_rag_service import search_relevant_chunks

    all_chunks: list[dict] = []  # {"file_name": str, "chunk": str, "score_order": int}

    for entry in ready_files:
        file_name = entry.get("original_name", "arquivo_desconhecido")
        extracted_path = entry.get("extracted_text_path", "")

        if not extracted_path or not Path(extracted_path).exists():
            logger.warning("[INVESTIGATOR] Arquivo %s sem texto extraido", file_name)
            continue

        try:
            text = await asyncio.to_thread(
                lambda p=extracted_path: open(p, "r", encoding="utf-8").read()
            )
        except Exception as e:
            logger.warning("[INVESTIGATOR] Falha ao ler %s: %s", file_name, e)
            continue

        if not text.strip():
            continue

        chunks = search_relevant_chunks(text, query, limit=_CHUNKS_PER_FILE)
        for i, chunk in enumerate(chunks):
            all_chunks.append({
                "file_name": file_name,
                "chunk": chunk.strip(),
                "score_order": i,
            })

    if not all_chunks:
        return (
            f"Nenhum trecho relevante encontrado nos {len(ready_files)} documento(s) "
            f"para a pergunta: \"{query}\". Tente reformular ou ser mais especifico."
        )

    # Limita chunks totais (prioriza os primeiros de cada arquivo)
    all_chunks.sort(key=lambda c: c["score_order"])
    if len(all_chunks) > _MAX_TOTAL_CHUNKS:
        all_chunks = all_chunks[:_MAX_TOTAL_CHUNKS]

    logger.info("[INVESTIGATOR] %d chunks coletados de %d arquivos", len(all_chunks), len(ready_files))

    # ── Passo C: Sintese via LLM ──────────────────────────────────────────────
    # Monta contexto com chunks agrupados por arquivo
    context_parts = []
    current_chars = 0
    for chunk_info in all_chunks:
        entry_text = f"[Fonte: {chunk_info['file_name']}]\n{chunk_info['chunk']}\n"
        if current_chars + len(entry_text) > _MAX_CONTEXT_CHARS:
            break
        context_parts.append(entry_text)
        current_chars += len(entry_text)

    context_text = "\n---\n".join(context_parts)

    # Nomes unicos de arquivos usados
    source_files = sorted(set(c["file_name"] for c in all_chunks))

    synthesis_prompt = (
        "Voce e um Investigador Forense de documentos. "
        "Com base EXCLUSIVAMENTE nos trechos de documentos fornecidos abaixo, "
        "responda detalhadamente a seguinte requisicao do usuario.\n\n"
        f"REQUISICAO: {query}\n\n"
        f"DOCUMENTOS ANALISADOS ({len(source_files)} arquivos):\n"
        + "\n".join(f"- {name}" for name in source_files)
        + f"\n\nTRECHOS RECUPERADOS:\n\n{context_text}\n\n"
        "REGRAS:\n"
        "1. Responda com base APENAS nos trechos acima. Nao invente informacoes.\n"
        "2. E OBRIGATORIO citar o [Nome do Arquivo] de onde voce tirou cada informacao.\n"
        "3. Se a informacao solicitada nao estiver nos trechos, diga explicitamente.\n"
        "4. Organize a resposta de forma clara, com topicos se necessario.\n"
        "5. NAO use ** ou # na formatacao. Use topicos simples com - ou numeracao."
    )

    try:
        model = registry.get_model("text_generator") or "openai/gpt-4o-mini"
        response = await call_openrouter(
            messages=[{"role": "user", "content": synthesis_prompt}],
            model=model,
            max_tokens=3000,
            temperature=0.2,
        )
        answer = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("[INVESTIGATOR] Falha na sintese LLM: %s", e)
        return f"Erro ao sintetizar resposta: {e}"

    if not answer:
        return "O LLM nao conseguiu gerar uma resposta. Tente reformular a pergunta."

    # Adiciona rodape com fontes
    footer = (
        f"\n\n---\nFontes consultadas ({len(source_files)} arquivo(s)): "
        + ", ".join(source_files)
    )
    if processing:
        footer += (
            f"\n(Nota: {len(processing)} arquivo(s) ainda em processamento "
            "nao foram incluidos nesta analise)"
        )

    return answer + footer
