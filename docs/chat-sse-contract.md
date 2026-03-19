# Chat SSE Contract

O endpoint principal de chat é `POST /api/agent/chat`.

O frontend envia:

- `messages`
- `mode`
- `session_id`
- `model`
- `system_prompt`
- `user_id`
- `project_id`
- `conversation_id`

O backend responde com `text/event-stream`.

## Eventos observados no frontend

Eventos consumidos em `pages/ArccoChat.tsx`:

- `conversation_id`
  Define a conversa persistente no backend.

- `chunk`
  Texto incremental da resposta final exibida no chat.

- `error`
  Erro terminal do processamento.

- `steps`
  Passos de execução usados pelo painel de pensamentos.

- `thought`
  Raciocínio resumido para UI de progresso.

- `browser_action`
  Estado intermediário do navegador headless.
  O `content` costuma ser um JSON serializado em string.

- `text_doc`
  Documento textual pronto para preview/exportação.
  O `content` costuma ser um JSON serializado em string com `title` e `content`.

- `file_artifact`
  Arquivo gerado detectado pelo backend.
  O `content` costuma ser um JSON serializado em string com `filename` e `url`.

## Origem dos eventos

- `backend/api/chat.py`
  Emite `conversation_id`, `chunk` e `error` no fluxo de chat normal.

- `backend/agents/orchestrator.py`
  Emite `steps`, `thought`, `browser_action`, `text_doc`, `file_artifact`, `chunk` e `error`.

- `backend/agents/deep_research.py`
  Também emite `steps` e `thought`.

## Observações importantes

- Nem todo evento carrega JSON estruturado diretamente.
  Em alguns casos o backend encapsula um JSON como string dentro de `content`.

- O frontend precisa tratar `chunk` como acumulativo.

- Mudanças em qualquer tipo de evento exigem alinhamento em:
  `backend/api/chat.py`
  `backend/agents/orchestrator.py`
  `backend/agents/deep_research.py`
  `lib/api-client.ts`
  `pages/ArccoChat.tsx`
