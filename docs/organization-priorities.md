# Organization Priorities

Este arquivo resume o que mais vale organizar sem mudar comportamento.

## 1. Estrutura e fronteiras

- Separar `pages/ArccoChat.tsx` em módulos por responsabilidade:
  estado da conversa, streaming SSE, projetos, anexos, previews e modais.
- Separar `pages/AdminPage.tsx` por domínio:
  usuários, API keys, agentes e modelos de chat.

## 2. Contratos

- Tipar melhor respostas do backend no frontend.
- Consolidar o contrato SSE em um ponto único.
- Padronizar `API_BASE` dos clients frontend para evitar mistura entre proxy relativo e localhost hardcoded.

## 3. Documentação operacional

- Manter README curto e deixar detalhes em `docs/`.
- Explicar:
  como projeto selecionado influencia a conversa,
  onde está a fonte de verdade de prompts/tools/modelos,
  quais dados vêm do Supabase direto e quais vêm do backend Python.

## 4. Qualidade do texto

- Corrigir arquivos com comentários e strings corrompidos por encoding.
- Evitar comentários longos em arquivos grandes quando eles repetem o código.
- Priorizar comentários só em invariantes, protocolo e decisões arquiteturais.

## 5. Hotspots atuais

- `pages/ArccoChat.tsx`
- `pages/AdminPage.tsx`
- `backend/agents/orchestrator.py`
- `backend/agents/registry.py`
- `backend/agents/tools.py`

## Regra prática

Se uma alteração tocar chat, revisar sempre:

- `pages/ArccoChat.tsx`
- `lib/api-client.ts`
- `backend/api/chat.py`
- `backend/agents/orchestrator.py`

Se tocar agentes/admin, revisar sempre:

- `pages/AdminPage.tsx`
- `backend/api/admin.py`
- `backend/agents/registry.py`
- `backend/agents/tools.py`
- `backend/agents/prompts.py`
