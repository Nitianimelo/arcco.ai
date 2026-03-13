# AI Memory

Este arquivo e a pasta `docs/ai-memory/` formam a memoria operacional compartilhada do projeto.

Qualquer IA que atuar neste repositorio deve:
- ler este arquivo antes de propor ou aplicar mudancas
- consultar o arquivo de memoria mais recente em `docs/ai-memory/`
- registrar um novo arquivo datado ao finalizar mudancas relevantes
- manter este indice curto e atualizado

## Estado atual

- Projeto full-stack da Arcco.ai com frontend em React + Vite + TypeScript e backend em FastAPI + Python.
- Integracoes principais visiveis no codigo: Supabase, OpenRouter, Tavily, OCR e servicos de arquivos/exportacao.
- O backend expoe rotas em `/api/agent` e `/api/admin`.
- O frontend parece consumir o backend local com Vite durante desenvolvimento.
- Este diretorio nao esta em um repositorio Git no momento da criacao desta memoria.

## Onde comecar

- Visao geral e setup: `README.md`
- Frontend: `package.json`, `pages/`, `components/`, `lib/`
- Backend: `backend/main.py`, `backend/api/`, `backend/agents/`, `backend/services/`
- Banco/storage: `supabase/migrations/`

## Convencao do historico

Cada entrada nova deve virar um arquivo proprio em `docs/ai-memory/` com nome:

`YYYY-MM-DD-HHMM-resumo-curto.md`

Exemplo:

`2026-03-12-1030-ajuste-streaming-chat.md`

## Ultima entrada

- [2026-03-12-1947-file-artifact-browser-streaming.md](docs/ai-memory/2026-03-12-1947-file-artifact-browser-streaming.md)

## Entradas recentes

- [2026-03-12-1947-file-artifact-browser-streaming.md](docs/ai-memory/2026-03-12-1947-file-artifact-browser-streaming.md)
- [2026-03-12-1803-sessao-efemera-rag.md](docs/ai-memory/2026-03-12-1803-sessao-efemera-rag.md)
- [2026-03-12-1244-criacao-ai-memory.md](docs/ai-memory/2026-03-12-1244-criacao-ai-memory.md)
- [2026-03-12-initial-context.md](docs/ai-memory/2026-03-12-initial-context.md)

## Template para novas entradas

```md
# Titulo curto

## Data
YYYY-MM-DD HH:MM

## Objetivo
O que foi pedido ou decidido.

## Arquivos alterados
- caminho/do/arquivo

## O que mudou
- resumo direto das mudancas

## Impacto
- comportamento afetado

## Validacao
- testes executados
- o que nao foi validado

## Pendencias
- riscos, duvidas ou proximos passos
```
