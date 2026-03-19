# CHANGELOG — Registro de Modificações por IA

> Toda IA que modificar código neste repositório DEVE registrar aqui.
> Formato: data/hora, arquivos modificados, o que foi feito, por quê.

---

## 2026-03-19 (17) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `components/chat/DesignGallery.tsx`

### O que foi feito:
1. **ArccoChat.tsx** — Importou `DesignPreviewModal`, adicionou state `designPreviewHtml`, conectou `onOpenPreview` callback no `renderContent()` para PresentationCard e DesignGallery, renderizou o modal popup condicionalmente.
2. **DesignGallery.tsx** — Adicionou prop `onOpenPreview` e repassa para cada PresentationCard. Removeu referencia a `galleryMode` (prop inexistente).

### Por que:
Conectar o fluxo completo: card compacto no chat -> click em "Visualizar" -> abre popup modal com editor/export. Sem isso os componentes estavam criados mas desconectados.

---

## 2026-03-19 (16) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `components/chat/PresentationCard.tsx` (REWRITE)
- `components/chat/DesignGallery.tsx` (NOVO)
- `pages/ArccoChat.tsx`
- `backend/agents/prompts.py`
- `src/index.css`

### O que foi feito:
1. **PresentationCard.tsx** — Rewrite completo do editor de design. Substituiu sidebar 320px por toolbar horizontal compacta (flex-wrap). Canvas unificado responsivo (maxWidth CSS, sem altura fixa). FloatingTextPanel absoluto para editar texto selecionado. Toggle segmentado Visualizar/Editar. Barra de progresso animada no export. Prop `galleryMode` para uso dentro do gallery. Corrigidos 8 bugs: alturas fixas h-[520px]/h-[560px], Math.min(860) hardcoded, z-50 conflitante, color pickers sem touch target, sidebar que não colapsava, sem feedback de modo edição, sem feedback de export.
2. **DesignGallery.tsx** — Novo componente para exibir multiplos designs. Barra de thumbnails numerados com scroll horizontal, navegacao prev/next, contador "1 de N", renderiza PresentationCard em galleryMode.
3. **ArccoChat.tsx** — renderContent() agora faz split por `<!-- ARCCO_DESIGN_SEPARATOR -->` e renderiza DesignGallery quando ha multiplos HTML designs. Import do DesignGallery adicionado.
4. **prompts.py** — Adicionada instrucao ao DESIGN_GENERATOR_SYSTEM_PROMPT para gerar multiplas pecas separadas pelo delimiter.
5. **index.css** — 3 animacoes novas: gallery-thumb-enter, float-panel-enter, editor-glow.

### Por que:
Editor anterior tinha UX ruim (sidebar 320px inutilizavel em tablet/mobile, alturas fixas quebravam em telas menores, zero feedback visual). Nao suportava multiplos designs. Redesenhado para ser canvas-first, intuitivo e responsivo, com suporte a galeria de artes.

---

## 2026-03-19 (15) — Claude Code (claude-opus-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Moveu `from backend.agents.tools import SUPERVISOR_TOOLS` para o topo do módulo (import global). Antes estava como import local dentro de `orchestrate_and_stream()`, mas era usado por `_call_supervisor_for_step()` (função separada) causando `NameError: name 'SUPERVISOR_TOOLS' is not defined`.

### Por quê:
Este era o BUG REAL que travava todo o fluxo de agentes. Quando o planner gerava um plano e tentava chamar o supervisor para executar o passo (web_search, browser, etc.), a função `_call_supervisor_for_step` falhava com NameError porque `SUPERVISOR_TOOLS` só existia no escopo local de `orchestrate_and_stream`. O erro era capturado pelo try/except e emitido como evento SSE de error, mas o pipeline morria ali. Testado com web_search (Tavily) e browser (Browserbase/OLX) — ambos funcionando perfeitamente com heartbeats em tempo real.

---

## 2026-03-19 (14) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`

### O que foi feito:
1. **orchestrator.py** — Substituiu 4 call sites de `_run_with_heartbeat` (quebrado) por `_exec_with_heartbeat` (async generator). Os 4 pontos: web_search no planner loop, browser no planner loop, web_search no react loop, browser no react loop. Removidas referências a `_HEAVY_TOOL_TIMEOUT` (agora `_BROWSER_TIMEOUT`).

### Por quê:
O `_run_with_heartbeat` coletava heartbeats numa lista e retornava tudo junto DEPOIS da tool terminar — o frontend nunca recebia eventos SSE durante a execução, causando timeout na conexão. O novo `_exec_with_heartbeat` é um async generator que yield heartbeats em tempo real.

---

## 2026-03-19 (13) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/agents/orchestrator.py`
- `backend/api/chat.py`
- `backend/services/browser_service.py`
- `backend/services/search_service.py`
- `backend/core/config.py`
- `backend/agents/prompts.py`

### O que foi feito:
1. **orchestrator.py** — 5 correções:
   - Browser com timeout+heartbeat: envolvido `execute_tool("ask_browser")` em `_run_with_heartbeat()` (timeout 60s, heartbeat SSE a cada 5s) nos 2 locais (planner loop e react loop). Impede hang infinito e mantém conexão SSE viva.
   - Web search com timeout+heartbeat: envolvido `execute_tool("web_search")` em `_run_with_heartbeat()` (timeout 30s, heartbeat SSE a cada 5s) nos 2 locais. `web_fetch` também com `asyncio.wait_for(timeout=20)`.
   - Fallback após falha de browser: no react loop, quando browser retorna erro, injeta system message instruindo o supervisor a NÃO tentar browser novamente e usar web_search ou responder diretamente.
   - Helper `_run_with_heartbeat()`: nova função que executa coroutine com heartbeat periódico e timeout global. Cancela a task se exceder o timeout.
   - Constante `_HEAVY_TOOL_TIMEOUT = 60.0` centralizada.
2. **chat.py** — Desbloqueio do event loop: todas as chamadas sync ao Supabase em `_build_extra_context()` agora rodam via `asyncio.to_thread()`: `db.query()`, `get_user_memory()`, `search_project_context()`. Antes, chamadas httpx sync bloqueavam o event loop inteiro do uvicorn, congelando TODOS os requests durante queries ao Supabase.
3. **browser_service.py** — Timeout global de 45s no `asyncio.to_thread(_run_sync_session)` via `asyncio.wait_for()`. Proteção extra caso o CDP connection ou o site trave.
4. **search_service.py** — 3 correções:
   - `search_web_formatted()`: timeout de 10s para `get_search_key()`, timeout de 15s para `search_tavily()`/`search_brave()`. Impede hang quando Supabase ou Tavily estão lentos.
   - `search_tavily()`: timeout httpx reduzido de 30s para 15s. Logs de início/fim de busca.
   - `search_brave()`: timeout httpx reduzido de 30s para 15s. Log de início de busca.
5. **config.py** — Logs explícitos no startup: se `browserbase_api_key` ou `browserbase_project_id` estiverem vazios, loga WARNING com instruções de como configurar. Se ambos OK, loga confirmação.
6. **prompts.py** — Prompt do planner reescrito: ferramentas listadas por prioridade de uso, web_search como PRIMEIRA OPÇÃO, browser marcado como CARO E LENTO com regra explícita de só usar quando web_search não resolve. Regra crítica adicionada: "Prefira SEMPRE web_search sobre browser."

7. **llm.py** — Removido loop `["ApiKeys", "apikeys"]` em `get_api_key()`, `get_search_key()` e `get_vercel_key()`. Agora consulta APENAS a tabela `ApiKeys` (CamelCase). A tabela `apikeys` (minúscula) foi removida do Supabase pelo usuário — queries à tabela inexistente geravam erros 404 e adicionavam latência desnecessária.
8. **config.py** — Removido loop de tabelas em `_load_keys_from_supabase()`. Query única à tabela `ApiKeys`. Adicionado log dos providers encontrados no Supabase.
9. **embedding_service.py** — Removido loop de tabelas em `_get_openai_key()`. Query única à tabela `ApiKeys`.
10. **search_service.py** — Removido todo o código do Brave Search (função `search_brave()`, parâmetro `brave_key`, fallback Brave). Agora usa exclusivamente Tavily.
11. **llm.py** — `get_search_key()` busca apenas `provider=tavily` (removido loop `["tavily", "brave"]`).
12. **api/search.py** — Atualizado docstring (removido referência ao Brave).

### Por quê:
- Fluxo quebrava nas ações de busca web E browser: sem timeout em NENHUMA tool do orchestrator, qualquer lentidão no Tavily, Supabase, Browserbase ou OpenRouter travava o pipeline inteiro sem limite de tempo. Sem heartbeat, a conexão SSE era dropada pelo proxy/browser após inatividade. Chamadas sync ao Supabase bloqueavam o event loop, congelando todo o backend. Planner roteava desnecessariamente para browser quando web_search bastava.
- Tabela `apikeys` (minúscula) foi removida do Supabase, mas o código tentava queries em ambas as tabelas. Cada query à tabela inexistente gerava erro HTTP e latência extra. Unificado para usar apenas `ApiKeys`.

---

## 2026-03-19 (12) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/chat/AgentThoughtPanel.tsx`
- `pages/ArccoChat.tsx`
- `backend/agents/orchestrator.py`
- `backend/core/llm.py`

### O que foi feito:
1. **AgentThoughtPanel.tsx** — Aumentou visibilidade: fundo `#111114` (era `#0a0a0b`), borda `#2e2e34` quando rodando (era `#1c1c1e`), texto do header `text-neutral-300` (era `text-neutral-400`), borda esquerda do step ativo `border-neutral-300` (era `border-neutral-400`), step done `text-neutral-500` (era `text-neutral-600`), `✓` `text-neutral-600` (era `text-neutral-700`).
2. **ArccoChat.tsx** — Adicionou `useEffect` que chama `messagesEndRef.current?.scrollIntoView` quando `browserAction` muda, garantindo que o `BrowserAgentCard` seja visível ao aparecer. Atualizou loader pré-step com mesmos valores de cor.
3. **orchestrator.py** — Corrigido travamento no web_search: após receber resultado da busca, injeta mensagem `role: system` instruindo o supervisor a sintetizar e responder sem chamar mais ferramentas. Reduzido `MAX_ITERATIONS` de 5 para 3 (reduz tempo máximo de hang de 5min para ~2.5min).
4. **llm.py** — Reduzido timeout de `call_openrouter` de 60s para 45s para failar mais rápido em caso de lentidão do OpenRouter.

### Por quê:
- Travamento 4min: supervisor recebia resultado da busca e entrava em loop chamando `ask_web_search` novamente até MAX_ITERATIONS. Fix: instrução explícita para responder + menos iterações + timeout menor.
- Browser card não visível: scroll não seguia o card (apenas seguia messages). Fix: novo useEffect.
- Terminal pouco visível: cores muito escuras para o estilo escuro do tema.
- ATENÇÃO: se o BrowserAgentCard sempre mostrar erro, verificar se `BROWSERBASE_API_KEY` e `BROWSERBASE_PROJECT_ID` estão configurados (tabela ApiKeys no Supabase, provider='browserbase').

---

## 2026-03-19 (11) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/chat/AgentThoughtPanel.tsx` (reescrito)
- `src/index.css`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **AgentThoughtPanel.tsx** — Reescrito do zero no estilo terminal monocromático (Manus-style). Removidos todos os ícones coloridos, `CheckCircle2` verde, `BrainCircuit`, `Sparkles`, `Loader2`, `shimmer-text`, `border-breathe`, `ring-pulse`, `success-flash`, `thought-glow`. Substituídos por: indicadores geométricos (`✓`, `·`, `▌`), fonte monospace, borda esquerda fina como indicador de estado, cursor `▌` piscante no step ativo, fundo `#0a0a0b`, header lowercase `agente · pensando` / `agente · concluído em Ns`. Thoughts indentados com fonte menor e itálico dim. Interface idêntica (mesmas props) — ArccoChat sem alterações estruturais.
2. **src/index.css** — Adicionada animação `@keyframes cursor-blink` e `.animate-cursor-blink` (1s step-end infinite) para o indicador `▌`.
3. **pages/ArccoChat.tsx** — Substituído o loader orbitante (3 dots coloridos + shimmer-text) antes do primeiro step pelo mesmo estilo terminal inline: `agente · pensando▌`.

### Por quê:
Usuário pediu UI agentic/clean no estilo Manus — sem ícones coloridos, sem animações chamativas, visual profissional e minimalista.

---

## 2026-03-19 (10) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/tools/__init__.py` (novo)
- `backend/tools/catalog.py` (novo)
- `backend/tools/README.md` (novo)
- `backend/api/tools.py` (novo)
- `backend/main.py`
- `pages/ToolsStorePage.tsx`

### O que foi feito:
1. **backend/tools/catalog.py** — Fonte da verdade das tools. Lista `TOOLS_CATALOG` com 14 tools (dicts com id, name, description, category, status, icon_name, color). Helpers `get_tool_by_id()` e `get_available_tools()`.
2. **backend/tools/README.md** — Guia completo de integração: passo a passo (5 passos), checklist, convenções, tabela de categorias, paleta de cores, tabela de ícones. Qualquer IA ou dev consegue adicionar uma tool seguindo o guia.
3. **backend/api/tools.py** — `GET /api/agent/tools` (lista completa) e `GET /api/agent/tools/{tool_id}` (tool por ID).
4. **backend/main.py** — Registrou `tools_api` router com prefix `/api/agent`.
5. **pages/ToolsStorePage.tsx** — Agora busca catálogo de `/api/agent/tools` ao montar. `icon_name` (string) é resolvido para componente Lucide via `ICON_MAP`. Mantém fallback local se API falhar. Indicador de loading no header.

### Por quê:
Criar estrutura centralizada no backend (VPS) para o catálogo de tools, com guia para que qualquer IA saiba como integrar uma nova tool sem precisar perguntar.

---

## 2026-03-19 (9) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/ToolsStorePage.tsx` (novo)
- `pages/MyToolsPage.tsx` (novo)
- `App.tsx`

### O que foi feito:
1. **ToolsStorePage.tsx** — Tela Loja de Tools com 14 tools catalogadas (Pesquisa, Código, Documentos, Automação, Análise, Em breve). Filtros por categoria, busca por texto, botão Adicionar/Remover. Seleção persiste em `localStorage` (chave `arcco_selected_tools`).
2. **MyToolsPage.tsx** — Tela Minhas Tools mostrando apenas as tools que o usuário adicionou. Botão X para remover individualmente. Estado vazio com CTA para a Loja. Sincroniza com `localStorage` (evento `storage` para múltiplas abas).
3. **App.tsx** — Importou `ToolsStorePage` e `MyToolsPage`. Adicionou cases `TOOLS_STORE` e `TOOLS_MY` no `renderContent()`. `MyToolsPage` recebe `onNavigateToStore` para navegar diretamente para a Loja.

### Por quê:
Implementação das telas de Tools solicitadas pelo usuário. UI apenas — sem backend. Lógica de seleção simples via localStorage.

---

## 2026-03-19 (8) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/core/supabase_client.py`
- `backend/api/conversations.py`

### O que foi feito:
1. **supabase_client.py** — `query()` agora trata valores `None` nos filtros como `is.null` (PostgREST). Antes usava `eq.None` que não funciona.
2. **conversations.py** — GET `/conversations` sem `project_id` agora filtra `project_id=is.null`, retornando apenas conversas do chat normal. Com `project_id` continua filtrando pelo projeto específico.

### Por quê:
Recentes da sidebar não deve exibir conversas de projetos. Conversas de projeto só aparecem ao clicar no projeto.

---

## 2026-03-19 (7) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `App.tsx`
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **App.tsx** — `handleNewInteraction` agora limpa `selectedProjectId` e `activeProject` antes de abrir nova sessão. Clicar em "Nova Interação" desvincula qualquer projeto ativo.
2. **Sidebar.tsx** — `loadSessions()` removeu todos os fallbacks de localStorage. Sem userId → array vazio. Com userId → somente `conversationApi.list(userId)`. `handleDeleteSession` não chama mais `chatStorage.deleteSession()`. Import de `chatStorage` removido (só `ChatSession` type permanece).
3. **ArccoChat.tsx** — `saveToSession()` virou no-op (backend já persiste via background task). Carregamento de sessão: se `chatSessionId` não for UUID → mensagens vazias (sem buscar localStorage). Import reduzido a só o type `Message`.

### Por quê:
Usuário pediu: histórico somente do Supabase, zero localStorage. "Nova Interação" deve fechar o projeto ativo e abrir chat limpo.

---

## 2026-03-19 (6) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `backend/api/projects.py`
- `backend/api/conversations.py`
- `lib/projectApi.ts`
- `lib/conversationApi.ts`
- `App.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **projects.py** — Adicionado `GET /projects/{id}` para buscar projeto por ID.
2. **conversations.py** — `GET /conversations` agora aceita `project_id` como query param opcional para filtrar conversas por projeto.
3. **projectApi.ts** — Adicionado método `get(projectId)`.
4. **conversationApi.ts** — `list()` aceita `projectId` opcional. Adicionado `findByProject(userId, projectId)`.
5. **App.tsx** — `useEffect` ao mudar `selectedProjectId`: carrega detalhes do projeto (`projectApi.get`), busca conversa existente do projeto (`findByProject`), carrega essa conversa ou inicia nova. Passa `project`, `onProjectUpdated`, `onProjectDeleted` para ArccoChatPage.
6. **ArccoChat.tsx** — Novas props `project`, `onProjectUpdated`, `onProjectDeleted`. Header exibe badge do projeto + botão de lápis. Greeting substitui por nome do projeto + trecho das instruções. Modal de edição completo: nome, instruções, lista de arquivos com delete, upload de novos arquivos, botão excluir projeto com confirmação dupla.

### Por quê:
Usuário pediu: chat se moldando ao projeto selecionado (1 conversa por projeto), botão de editar configurações do projeto (nome, instruções, arquivos, modelo), botão de excluir.

---

## 2026-03-19 (5) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/Sidebar.tsx`
- `lib/conversationApi.ts`
- `lib/preferencesApi.ts`
- `lib/projectApi.ts`

### O que foi feito:
1. **Sidebar.tsx** — Refatorou `useEffect` de histórico: extraiu lógica em `loadSessions()` e adicionou `setInterval(loadSessions, 15000)` para polling a cada 15s com ou sem userId. Antes, quando userId estava presente, carregava só uma vez e nunca atualizava.
2. **conversationApi.ts / preferencesApi.ts / projectApi.ts** — Corrigiu `API_BASE` de `http://localhost:8001/api/agent` para `/api/agent` (caminho relativo via Vite proxy). URL hardcoded quebraria em produção.

### Por quê:
Novas conversas criadas pelo chat não apareciam no histórico da Sidebar porque a lista era carregada apenas no mount. Polling de 15s garante que a Sidebar reflita conversas recentes sem precisar recarregar a página. URLs hardcoded corrigidas para funcionar em qualquer ambiente.

---

## 2026-03-19 (4) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `pages/AdminPage.tsx`

### O que foi feito:
1. **AdminPage.tsx** — Adicionado `openai` no mapa `PROVIDER_ICONS` e no dropdown de providers do formulário de nova API key. Antes só existiam: `openrouter`, `anthropic`, `browserbase`, `browserbase_project_id`.

### Por quê:
Usuário não conseguia adicionar a chave da OpenAI pelo painel admin porque a opção "OpenAI" não existia no dropdown.

---

## 2026-03-19 (3) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados/criados:
- `migrations/004_pgvector.sql` *(criado)*
- `backend/services/embedding_service.py` *(criado)*
- `backend/services/project_rag_service.py` *(reescrito)*

### O que foi feito:
1. **004_pgvector.sql** — Migration para habilitar `pgvector`, dropar coluna `chunk_tsv` (FTS), adicionar `embedding vector(1536)`, criar índice HNSW (`vector_cosine_ops`, m=16, ef=64) e criar função RPC `search_project_chunks(p_project_id, p_embedding, p_top_k)` que retorna `chunk_text` + `similarity` ordenados por distância coseno.
2. **embedding_service.py** — Novo serviço. `get_embedding(text)` e `get_embeddings_batch(texts)` chamam OpenAI API (`text-embedding-3-small`, 1536 dims) via httpx. API key buscada da tabela `ApiKeys` (provider='openai') com fallback para env var `OPENAI_API_KEY`. Cache da key em memória.
3. **project_rag_service.py** — Reescrito. `insert_chunks_for_file()` agora gera embeddings em batch (100/chamada) e insere com coluna `embedding`. `search_project_context()` gera embedding da query e chama RPC `search_project_chunks` via `db.rpc()`. FTS removido completamente.

### Por quê:
Usuário solicitou migração de FTS (keyword search) para pgvector (busca semântica por similaridade), que é a abordagem usada em produção (inclusive pela Anthropic no Claude). pgvector encontra contexto por significado mesmo quando palavras exatas não batem, e usa menos tokens pois retorna chunks mais precisos.

---

## 2026-03-19 (2) — Claude Code (claude-sonnet-4-6)

### Arquivos modificados:
- `components/Sidebar.tsx`
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **Sidebar.tsx** — `handleCreateProject()` agora faz upload dos arquivos selecionados para o backend via `projectApi.uploadFile()` após criar o projeto. Adicionado spinner de loading + status de upload no modal. Histórico agora carrega do Supabase como fonte principal (fallback localStorage). `handleDeleteSession` remove visualmente sem reload.
2. **ArccoChat.tsx** — ao clicar em conversa do histórico: detecta UUID (Supabase) vs timestamp (localStorage) e carrega mensagens da fonte correta.

### Por quê:
Arquivos do popup de projeto não estavam chegando ao backend (apenas no estado local React). RAG de projetos agora funciona de fato. Histórico do sidebar agora vem do Supabase.

---

## 2026-03-19 — Claude Code (claude-sonnet-4-6)

### Arquivos modificados/criados:
- `migrations/003_history_projects_preferences_memory.sql` *(criado)*
- `backend/core/supabase_client.py` *(modificado — métodos insert/update/upsert/delete/insert_many/rpc + fix upsert on_conflict)*
- `backend/models/schemas.py` *(modificado — novos schemas Conversation/Message/Project/Preferences, extended ChatRequest)*
- `backend/api/preferences.py` *(criado)*
- `backend/api/conversations.py` *(criado)*
- `backend/api/projects.py` *(criado)*
- `backend/api/chat.py` *(reescrito — injeção de contexto + conversation_id SSE + background task memória)*
- `backend/services/project_file_service.py` *(criado)*
- `backend/services/project_rag_service.py` *(criado — FTS PostgreSQL)*
- `backend/services/memory_service.py` *(criado — gpt-4o-mini síntese)*
- `backend/main.py` *(modificado — 3 novos routers)*
- `lib/preferencesApi.ts` *(criado)*
- `lib/projectApi.ts` *(criado)*
- `lib/conversationApi.ts` *(criado)*
- `lib/api-client.ts` *(modificado — userId/projectId/conversationId no chat())*
- `components/SettingsModal.tsx` *(modificado — carrega/salva preferências via Supabase)*
- `components/Sidebar.tsx` *(modificado — projetos via backend, selectedProjectId, userId prop)*
- `App.tsx` *(modificado — userId/selectedProjectId states, passados para Sidebar e ArccoChat)*
- `pages/ArccoChat.tsx` *(modificado — userId/projectId props, conversationId state, captura SSE conversation_id)*

### O que foi feito:
1. **SQL migration** — 6 novas tabelas: projects, conversations, messages, project_files, project_file_chunks (FTS), user_preferences, user_memory.
2. **supabase_client.py** — 6 novos métodos CRUD + corrigido upsert (on_conflict como query param, não header Prefer).
3. **chat.py** — Injeta custom_instructions, memória e RAG antes de chamar o orquestrador; emite `conversation_id` como primeiro evento SSE; salva histórico + atualiza memória via asyncio.ensure_future.
4. **project_rag_service.py** — Busca FTS via PostgREST `wfts(portuguese)`, insere chunks em batches de 50.
5. **project_file_service.py** — Upload para bucket `project-files`, extração em background task, chunks indexados no FTS.
6. **memory_service.py** — gpt-4o-mini sintetiza fatos permanentes com limite rígido de 1500 chars.
7. **Frontend** — Sidebar conectado ao backend de projetos; SettingsModal carrega/salva preferências do Supabase; ArccoChat passa userId/projectId/conversationId na chamada de chat.

### Por quê:
Implementação completa da camada de persistência: histórico de conversas, projetos com RAG (FTS), preferências do usuário e memória acumulativa do usuário — tudo integrado ao Supabase.

---

## 2026-03-12 21:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/executor.py`
- `backend/agents/orchestrator.py`
- `backend/core/llm.py`
- `backend/api/export.py`
- `backend/agents/prompts.py`

### O que foi feito:
1. **executor.py** — Moveu `from e2b_code_interpreter import Sandbox` para dentro de try/except ImportError. Corrigiu `execution_result.text or ""` (era None).
2. **orchestrator.py** — Adicionou `_PLANNER_ACTION_TO_TOOL` map e `tool_choice` forçado no Planner loop. Adicionou try/except em todas as execuções de tools. Removeu segunda chamada LLM na consolidação final (streaming direto de `message["content"]`). Corrigiu `accumulated_context` para incluir resultado real do browser.
3. **llm.py** — Adicionou parâmetro `tool_choice=None` em `call_openrouter()`.
4. **export.py** — Adicionou fallback reportlab quando Playwright indisponível para PDF.
5. **prompts.py** — Adicionou regras de formatação no CHAT_SYSTEM_PROMPT proibindo `**` e `#`.

### Por quê:
3 bugs críticos: E2B não executava, loop crashava na consolidação, browser agent não aparecia. PDF export falhava. Respostas vinham com markdown.

---

## 2026-03-13 08:30 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/executor.py`

### O que foi feito:
1. **executor.py** — Reescreveu `_execute_python()` para API E2B v2.4.1: `Sandbox.create(api_key=...)` ao invés do construtor. Captura stdout de `result.logs.stdout` (print). Captura expressões de `result.text`. Sandbox destruído com `.kill()` no finally.

### Por quê:
E2B v2.4.1 mudou a API. `Sandbox(api_key=...)` dava erro. `result.text` era None para print(). Testado e confirmado funcionando com sandbox cloud.

---

## 2026-03-13 08:50 — Claude Code (Sonnet)

### Arquivos modificados:
- `backend/agents/prompts.py`
- `backend/agents/registry.py`
- `backend/agents/planner.py`
- `backend/agents/orchestrator.py`
- `backend/api/admin.py`

### O que foi feito:
1. **prompts.py** — Adicionou `PLANNER_SYSTEM_PROMPT` como constante separada.
2. **registry.py** — Adicionou agente `planner` (7o agente) com modelo `openai/gpt-4o-mini` e import do PLANNER_SYSTEM_PROMPT.
3. **planner.py** — Trocou prompt hardcoded por `registry.get_prompt("planner")`.
4. **orchestrator.py** — Trocou `supervisor_model` por `registry.get_model("planner")` na chamada do Planner.
5. **admin.py** — Adicionou `"planner": "PLANNER_SYSTEM_PROMPT"` em `_PROMPT_CONSTANTS`. Adicionou `"planner"` nos DEFAULTS do `reset_agent` com import.

### Por quê:
Planner usava o mesmo modelo caro do Supervisor (claude-3.5-sonnet). Agora usa modelo leve (gpt-4o-mini) editável pelo admin. Economia de tokens + velocidade. Planner visível no admin como 7o agente.

---

## 2026-03-13 09:15 — Claude Code (Sonnet)

### Arquivos modificados:
- `components/chat/TextDocCard.tsx`
- `components/chat/DocumentPreviewModal.tsx` (novo)
- `pages/ArccoChat.tsx`

### O que foi feito:
1. **TextDocCard.tsx** — Redesenhado como card compacto. Removeu editor inline. Adicionou `onOpenPreview` callback e botão "Preview".
2. **DocumentPreviewModal.tsx** — Criado novo componente. Modal overlay com textarea editável para text_doc, iframe para PDF/Excel. Fullscreen toggle, ESC para fechar, contagem de palavras, botões DOCX/PDF no footer.
3. **ArccoChat.tsx** — Removeu side panel de 45%. Adicionou estado `modalPreview`. FilePreviewCard e TextDocCard agora abrem DocumentPreviewModal. Melhorou visual do FilePreviewCard. Chat ocupa 100% largura.

### Por quê:
Usuário pediu preview em popup ao invés de side panel, com ambiente mais textual para edição de documentos.

---

## 2026-03-13 10:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `CLAUDE.md`

### O que foi feito:
1. **CLAUDE.md** — Reescrito completamente. Atualizado com 7 agentes, pipeline Planner→Supervisor, TOOL_MAP, dependências E2B/Browserbase, regras de edição.

### Por quê:
CLAUDE.md estava desatualizado (5 agentes, pipeline antigo). Qualquer IA que abrir o repo precisa do estado real.

---

## 2026-03-13 15:00 — Claude Code (Sonnet)

### Arquivos modificados:
- `pages/ArccoChat.tsx`
- `pages/LoginPage.tsx`
- `pages/RegisterPage.tsx`
- `pages/ArccoDrive.tsx`
- `pages/AdminPage.tsx`
- `components/Sidebar.tsx`
- `components/SettingsModal.tsx`
- `components/ui/DotGridBackground.tsx` (novo)
- `components/chat/AgentThoughtPanel.tsx`
- `components/chat/BrowserAgentCard.tsx`
- `components/chat/DocumentPreviewModal.tsx`
- `components/chat/TextDocCard.tsx`
- `backend/api/location.py` (novo)
- `backend/main.py`
- `src/index.css`
- `index.tsx`
- `App.tsx`

### O que foi feito:
1. **DotGridBackground.tsx** — Novo componente substituindo CircuitBackground. Grid de linhas estilo Vercel + 2 glows radiais com CSS vars.
2. **index.css** — CSS custom properties para 3 temas (`--bg-base`, `--dot-color`, `--glow-primary`, etc.) aplicados via `[data-theme]` no `<html>`.
3. **index.tsx** — Aplica tema salvo antes do React renderizar (sem flash).
4. **SettingsModal.tsx** — ThemePicker com 3 opções (Dark/Dim/Midnight), persiste em localStorage e aplica `data-theme`.
5. **ArccoChat.tsx** — Textarea com auto-resize (scrollHeight, máx 200px). Mode toggle movido para header. Logo inline ao lado do greeting. Pool de 10 sugestões rotativas por horário. Badge de clima/localização acima da saudação. Subtitle com cidade integrada.
6. **AgentThoughtPanel.tsx** — Estado concluído exibe pills compactos; "Concluído em Xs"; expandir ao clicar; reset ao iniciar nova execução.
7. **BrowserAgentCard.tsx** — Cursor mais suave (`duration-[180ms]`), viewport `h-60`, semáforos corretos por estado.
8. **DocumentPreviewModal.tsx** — Preview estilo documento (serif, bg escuro), footer com contador palavras/chars e botões Word/PDF com ícones coloridos.
9. **location.py** — Novo endpoint `GET /api/agent/location`. Proxy server-side para `ipwho.is` + `Open-Meteo`. Evita bloqueio Safari ITP.
10. **main.py** — Registrou `location_api.router` em `/api/agent`.

### Por quê:
Série de melhorias de UX solicitadas: background Vercel-style, sistema de temas, input auto-resize, saudação personalizada por horário/local, componentes do agente mais compactos. Localização via backend para contornar Safari ITP que bloqueava fetch direto para `ipwho.is`.
