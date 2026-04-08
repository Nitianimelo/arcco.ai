# Arcco.ai

Plataforma proprietária da **Arcco.ai** para chat com IA, agentes orquestrados, geração de arquivos e cofre de artefatos.

## Visão geral

Este repositório contém:

- frontend em React + Vite + TypeScript
- backend em FastAPI + Python
- integração com Supabase para autenticação, banco e storage
- integração com OpenRouter para modelos LLM
- agentes especializados para chat, busca, arquivos e OCR

## Estrutura principal

```text
backend/
  api/          Endpoints HTTP e SSE
  agents/       Registry, prompts, tools e orquestrador
  core/         Configuração, LLM e clientes base
  services/     Busca, OCR, browser e geração de arquivos
components/     UI reutilizável do frontend
pages/          Páginas principais do produto
lib/            Clientes e serviços usados pelo frontend
supabase/       Migrações e suporte ao banco/storage
```

## Fluxo do produto

- `Arcco Chat`: conversa com o usuário via SSE e delega tarefas aos agentes do backend.
- `Arcco Drive`: lista e gerencia arquivos gerados ou salvos no storage.
- `Admin`: permite gerenciar usuários, API keys e configurações dos agentes.

## Requisitos

- Node.js 20+
- Python 3.11+ ou 3.12
- credenciais válidas de Supabase
- chave ativa do OpenRouter

## Variáveis de ambiente

As variáveis mais importantes estão em `.env` e `.env.example`.

Backend:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
CORS_ORIGINS=http://localhost:3000
AGENT_WORKSPACE=
TAVILY_API_KEY=
STEEL_API_KEY=
```

Frontend:

```env
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_TAVILY_API_KEY=
```

## Rodando localmente

### 1. Backend

```bash
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

Atalhos úteis:

- documentação: `http://localhost:8001/docs`
- healthcheck: `http://localhost:8001/health`

### 2. Frontend

```bash
npm install
npm run dev
```

O Vite sobe em `http://localhost:3000` e faz proxy para o backend em `http://localhost:8001`.

## Observações de manutenção

- O contrato de streaming do chat é SSE. Mudanças no backend exigem alinhamento com o consumer TypeScript.
- O registry em `backend/agents/registry.py` é a fonte de verdade dos agentes carregados em runtime.
- O README anterior estava desatualizado e referenciava AI Studio/Gemini; este arquivo agora descreve a arquitetura real do projeto.

## Documentação interna

- `docs/architecture-overview.md`: mapa do app e hotspots
- `docs/chat-sse-contract.md`: contrato de eventos entre backend e frontend
- `docs/organization-priorities.md`: prioridades de organização sem alterar comportamento
