# Sessao Efemera e RAG Lexical

## Data
2026-03-12 18:03

## Objetivo
Implementar upload efemero por sessao, extracao assincrona, leitura por tool calling, RAG lexical simples, GC por TTL e integrar o frontend ao novo fluxo sem injetar OCR direto no chat.

## Arquivos alterados
- backend/models/schemas.py
- backend/requirements.txt
- backend/api/files.py
- backend/api/chat.py
- backend/agents/tools.py
- backend/agents/executor.py
- backend/agents/orchestrator.py
- backend/agents/prompts.py
- backend/services/session_file_service.py
- backend/services/session_extraction_service.py
- backend/services/ephemeral_rag_service.py
- backend/services/session_gc_service.py
- lib/api-client.ts
- pages/ArccoChat.tsx

## O que mudou
- Criadas rotas de upload/listagem/remocao de arquivos efemeros por sessao em `/api/agent/session-files`.
- Implementado `manifest.json` por sessao em `/tmp/arcco_chat/{session_id}/` com status por arquivo.
- Extração assincrona passou a gerar `*_extracted.txt` em background.
- PDF agora tenta leitura nativa e, se `PyMuPDF` nao estiver disponivel, faz fallback para `PyPDF2`.
- Adicionada a tool `read_session_file(session_id, file_name, query?)`.
- Implementado RAG lexical simples com chunking e ranqueamento por frequencia de termos.
- Orquestrador passou a injetar inventario leve dos anexos e repassar `session_id`.
- Implementado GC por TTL com base em `updated_at` do manifesto.
- Frontend passou a anexar arquivos via backend e manter status visual `processando/pronto/falhou`.
- Removida a injecao automatica do texto extraido dentro da mensagem do usuario.
- Frontend agora exibe toast quando um anexo falha no processamento.

## Impacto
- O LLM consulta anexos sob demanda via tool calling, sem despejar OCR no historico do chat.
- Upload retorna rapido, e o trabalho pesado roda em background.
- PDFs com texto embutido funcionam mesmo sem `PyMuPDF` instalado.
- PDFs escaneados ainda dependem de OCR com renderizacao por `PyMuPDF` para melhor cobertura.

## Validacao
- `python3 -m py_compile` nos arquivos Python alterados.
- Smoke tests locais para manifesto, upload, extração, tool `read_session_file`, inventario de sessao e GC por TTL.
- Teste real com LLM fora do sandbox: o supervisor consultou `read_session_file` e respondeu corretamente a multa do contrato anexado.
- `npm run build` no frontend concluido com sucesso.

## Pendencias
- Remocao individual de anexos ainda nao existe no backend/frontend.
- OCR de PDFs escaneados fica limitado se `PyMuPDF` nao estiver instalado no ambiente de runtime.
- Vale adicionar testes automatizados de API para upload/processamento/listagem.
