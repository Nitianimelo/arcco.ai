# Contexto inicial do projeto

## Data
2026-03-12

## Objetivo
Criar a memoria compartilhada inicial para reduzir leitura repetitiva do repositorio por futuras IAs.

## Arquivos alterados
- AI_MEMORY.md
- docs/ai-memory/2026-03-12-initial-context.md

## Visao atual do sistema

- Frontend em React + Vite + TypeScript.
- Backend em FastAPI + Python.
- Supabase usado para autenticacao, banco e storage, conforme README e arquivos `lib/` e `supabase/`.
- OpenRouter aparece como integracao principal de LLM.
- Existem servicos e rotas para chat, busca, arquivos, OCR, exportacao e administracao.

## Estrutura relevante

- `pages/`: telas principais como chat, admin, login, registro e drive.
- `components/`: componentes reutilizaveis, incluindo componentes de chat.
- `lib/`: clientes e servicos do frontend, incluindo Supabase, OpenRouter, Tavily e arquivos.
- `backend/api/`: endpoints HTTP e SSE.
- `backend/agents/`: planner, orchestrator, executor, tools, prompts e registry.
- `backend/services/`: busca, browser, OCR, arquivos e modelos de chat.
- `supabase/migrations/`: migracoes relacionadas a banco e buckets.

## Observacoes tecnicas iniciais

- `backend/main.py` registra rotas com prefixos `/api/agent` e `/api/admin`.
- O backend possui healthcheck em `/health` e redireciona `/` para `/docs`.
- O README indica que o chat usa SSE; mudancas de contrato no backend exigem alinhamento com o frontend.
- O README tambem indica que `backend/agents/registry.py` e a fonte de verdade dos agentes carregados.
- O projeto possui `docker-compose.yml`, `Dockerfile.frontend` e `Dockerfile.backend`, mas nao foram validados nesta etapa.
- O diretorio nao estava inicializado como repositorio Git quando esta memoria foi criada.

## Dependencias visiveis rapidamente

Frontend:
- React 19
- Vite 6
- Supabase JS
- pdfjs-dist
- tesseract.js
- pptxgenjs
- jszip

Backend:
- FastAPI
- Uvicorn
- configuracao central em `backend/core/config.py`

## Validacao

- Estrutura de arquivos listada com `rg --files`.
- `README.md`, `package.json` e `backend/main.py` foram lidos para compor esta entrada.
- Nao foram executados frontend, backend, testes automatizados ou migracoes.

## Pendencias

- Descobrir fluxo real de autenticacao entre frontend e backend.
- Confirmar como SSE do chat e consumido no frontend.
- Mapear pontos exatos de persistencia no Supabase.
- Registrar futuras mudancas sempre em novos arquivos datados, sem sobrescrever esta entrada.
