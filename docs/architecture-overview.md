# Architecture Overview

Este projeto é um app full-stack com frontend React/Vite na raiz do repositório e backend FastAPI em `backend/`.

## Estrutura real

Frontend:

- `App.tsx`: ponto de entrada da aplicação autenticada.
- `components/Sidebar.tsx`: navegação principal, projetos e histórico.
- `pages/ArccoChat.tsx`: principal orquestrador de UI do chat.
- `pages/ArccoDrive.tsx`: cofre de arquivos do usuário.
- `pages/AdminPage.tsx`: CRUD operacional de usuários, API keys e agentes.
- `lib/*.ts`: clientes HTTP, Supabase e serviços auxiliares consumidos pelo frontend.

Backend:

- `backend/main.py`: sobe FastAPI e registra routers.
- `backend/api/chat.py`: endpoint central do chat e streaming SSE.
- `backend/agents/orchestrator.py`: fluxo supervisor-worker e emissão de eventos para o frontend.
- `backend/agents/registry.py`: fonte de verdade em runtime para prompts, modelos e tools.
- `backend/services/*`: memória, RAG, arquivos, OCR, browser e utilidades.

Persistência:

- Supabase tabela `User`: autenticação própria do app.
- Supabase tabela `ApiKeys`: chaves operacionais do backend/frontend.
- Supabase tabelas `conversations`, `messages`, `projects`, `project_files`, `user_preferences`.
- Supabase Storage: artefatos gerados e arquivos do usuário.

## Fluxos principais

1. Login/registro:
   O frontend lê/grava dados do usuário em `localStorage` e na tabela `User`.

2. Chat:
   `pages/ArccoChat.tsx` envia mensagens para `/api/agent/chat` via `lib/api-client.ts`.
   O backend monta contexto adicional, chama o orquestrador e devolve eventos SSE.

3. Projetos:
   A sidebar seleciona um projeto.
   `App.tsx` carrega detalhes do projeto e tenta reutilizar a conversa associada.

4. Admin:
   A tela `/admin` acessa diretamente Supabase para usuários/API keys e backend para agentes/modelos.

## Hotspots de manutenção

- `pages/ArccoChat.tsx`: concentra muitas responsabilidades.
- `pages/AdminPage.tsx`: alta densidade de UI + integração.
- `backend/agents/orchestrator.py`: lógica central do produto.
- `backend/agents/registry.py` + `backend/agents/tools.py`: configuram o comportamento dos agentes.
