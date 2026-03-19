# CLAUDE.md — Guia de Referência do Repositório Arcco

> Leia este arquivo inteiro antes de sugerir ou fazer qualquer mudança.

---

## 1. O QUE É O ARCCO

Arcco é uma plataforma SaaS de IA focada em chat inteligente com agentes autônomos.

| Produto | O que faz |
|---|---|
| **Arcco Chat** | Chat principal com agentes autônomos (busca web, geração de arquivos, execução Python, browser) |
| **Arcco Drive** | Cofre de arquivos gerados |

**Stack:** React 19 + Vite + TypeScript + Tailwind CSS (frontend) · FastAPI + Python 3.11 (backend) · Supabase (DB/storage) · OpenRouter (LLM gateway) · E2B (Python sandbox) · Browserbase (headless browser)

---

## 2. ESTRUTURA DE ARQUIVOS

```
arcco.ai.agentV1-master/
│
├── backend/
│   ├── main.py                     # Entry point — monta todos os routers
│   ├── core/
│   │   ├── config.py               # Variáveis de ambiente (.env / Supabase)
│   │   ├── llm.py                  # call_openrouter(), stream_openrouter() — suporta tool_choice
│   │   └── supabase_client.py      # Cliente Supabase leve (httpx)
│   ├── agents/
│   │   ├── registry.py             # 7 agentes: chat, planner, web_search, text_generator, design_generator, file_modifier, qa
│   │   ├── prompts.py              # System prompts (7 constantes, editáveis via admin)
│   │   ├── tools.py                # Definições JSON das ferramentas (SUPERVISOR_TOOLS, etc.)
│   │   ├── planner.py              # Gera plano JSON via modelo leve (PlannerOutput)
│   │   ├── orchestrator.py         # Pipeline: Planner → Supervisor ReAct → Workers
│   │   └── executor.py             # Executa tools: E2B Python, Browser, Files, Web Search
│   ├── api/
│   │   ├── chat.py                 # POST /api/agent/chat → orchestrate_and_stream()
│   │   ├── admin.py                # Admin API: GET/PUT/reset agentes, GET models
│   │   ├── export.py               # POST /api/agent/export-doc, export-html
│   │   ├── search.py               # POST /api/agent/search
│   │   ├── files.py                # POST /api/agent/files (PDF, Excel, PPTX)
│   │   ├── ocr.py                  # POST /api/agent/ocr
│   │   └── router.py               # POST /api/agent/route
│   └── services/
│       ├── search_service.py       # Integração Tavily
│       ├── file_service.py         # PDF (Playwright/reportlab), Excel, PPTX, DOCX
│       ├── ocr_service.py          # OCR de imagens
│       ├── browser_service.py      # Browserbase + Playwright CDP
│       └── chat_models.py          # CRUD de slots de chat mode
│
├── pages/
│   ├── ArccoChat.tsx               # Chat principal (SSE consumer, cards, preview modal)
│   └── AdminPage.tsx               # Painel admin (4 abas)
│
├── components/
│   ├── Sidebar.tsx                 # Navegação lateral
│   ├── AgentTerminal.tsx           # Painel de steps do agente
│   ├── Toast.tsx                   # Sistema de notificações
│   └── chat/
│       ├── TextDocCard.tsx         # Card de documento com preview/download
│       ├── DocumentPreviewModal.tsx # Modal popup para preview/edição de docs
│       ├── PresentationCard.tsx    # Card compacto de design (miniatura + botão Visualizar)
│       ├── DesignPreviewModal.tsx  # Modal popup para preview/edição/export de designs
│       ├── DesignGallery.tsx       # Galeria de múltiplos designs (thumbnails + navegação)
│       ├── BrowserAgentCard.tsx    # Card do browser agent (estilo Manus)
│       ├── AgentThoughtPanel.tsx   # Painel de steps em tempo real
│       └── ArtifactCard.tsx        # Card de código/JSON
│
├── lib/
│   ├── supabase.ts                 # Cliente Supabase frontend
│   ├── api-client.ts               # agentApi — wrappers para endpoints
│   ├── chatStorage.ts              # Persistência de histórico (localStorage)
│   ├── openrouter.ts               # OpenRouter LLM gateway wrapper
│   ├── driveService.ts             # Arcco Drive (salvar artefatos)
│   └── tavily.ts                   # Cliente Tavily
│
├── App.tsx                         # Router: /admin → AdminPage, / → ArccoChat
├── index.tsx                       # Entrypoint React
├── types.ts                        # Tipos TypeScript globais
└── CLAUDE.md                       # Este arquivo
```

---

## 3. PIPELINE SSE — ARCCO CHAT

```
Frontend (ArccoChat.tsx)
  → POST /api/agent/chat { messages, mode, session_id }
  → orchestrate_and_stream()  [orchestrator.py]
      │
      ├─ 1. PLANNER (modelo leve: gpt-4o-mini via registry "planner")
      │     → generate_plan(user_intent) → PlannerOutput { is_complex, steps[] }
      │
      ├─ 2a. is_complex=true → PLANNER LOOP
      │     → Itera steps com tool_choice forçado por step.action
      │     → accumulated_context passa entre steps
      │
      └─ 2b. is_complex=false → REACT LOOP (Supervisor com SUPERVISOR_TOOLS)
            → MAX_ITERATIONS loop com tool calls
```

**Eventos SSE:** `steps` | `chunk` | `thought` | `browser_action` | `text_doc` | `file_artifact` | `error`

**TOOL_MAP** (orchestrator.py):
- Terminal (resultado direto ao frontend): `ask_text_generator`, `ask_design_generator`
- Non-terminal (volta ao Supervisor): `ask_web_search`, `ask_browser`, `execute_python`, `deep_research`, `ask_file_modifier`, `read_session_file`

---

## 4. SISTEMA DE AGENTES — REGISTRY

**Arquivo central:** `backend/agents/registry.py` — 7 agentes editáveis via admin

| agent_id | Modelo default | Função |
|---|---|---|
| `chat` | anthropic/claude-3.5-sonnet | Supervisor principal (conversa + tools) |
| `planner` | openai/gpt-4o-mini | Gera plano JSON (modelo leve, economia de tokens) |
| `web_search` | openai/gpt-4o-mini | Busca web via Tavily |
| `text_generator` | openai/gpt-4o-mini | Gera documentos de texto bruto |
| `design_generator` | anthropic/claude-3.5-sonnet | Gera HTML/CSS visual |
| `file_modifier` | openai/gpt-4o-mini | Modifica arquivos existentes |
| `qa` | openai/gpt-4o-mini | Valida output dos especialistas |

**Admin Panel:** Acessível em `/admin` → aba "Orquestração"
- Editar prompt, modelo, tools de qualquer agente
- Prompts são reescritos direto em `prompts.py` (regex)
- Tools reescritos em `tools.py` (AST)
- Modelos salvos em `configs_override.json`

---

## 5. VARIÁVEIS DE AMBIENTE

```env
OPENROUTER_API_KEY=...      # Carregada do Supabase (tabela ApiKeys)
OPENROUTER_MODEL=...        # Modelo default (override pelo registry)
SUPABASE_URL=...
SUPABASE_KEY=...
CORS_ORIGINS=...
TAVILY_API_KEY=...
E2B_API_KEY=...             # Obrigatório para execução Python (sandbox cloud)
```

---

## 6. COMO RODAR LOCALMENTE

```bash
# Backend (porta 8001)
E2B_API_KEY="sua_chave" uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (porta 3000)
npm run dev
```

**Dependências Python extras:** `e2b-code-interpreter`, `browserbase`, `playwright`
```bash
pip install e2b-code-interpreter browserbase playwright
playwright install chromium
```

---

## 7. REGRAS PARA EDIÇÃO

1. **Nunca altere o contrato SSE** sem atualizar emitter (Python) e consumer (TypeScript)
2. **O registry é a fonte da verdade** para prompts/modelos em produção
3. **`configs_override.json`** é gerado automaticamente pelo admin — não commitar manualmente
4. **Respostas ao usuário:** nunca retornar `**`, `#` ou markdown (exceto links `[texto](url)`)
5. **E2B v2.4.1:** usar `Sandbox.create(api_key=...)`, não o construtor. Output de print() está em `result.logs.stdout`
6. **Export PDF:** tem fallback reportlab quando Playwright não está disponível
7. **Tools no orchestrator:** sempre dentro de try/except para não matar o generator SSE

---

## 8. CHANGELOG OBRIGATÓRIO

**Após qualquer modificação de código, registre em `AI_CHANGELOG.md` (dentro do repositório).**

Arquivo: `AI_CHANGELOG.md` (no mesmo diretório deste CLAUDE.md)

Formato obrigatório:
```
## AAAA-MM-DD HH:MM — [Nome da IA] ([Modelo])

### Arquivos modificados:
- `caminho/arquivo.ext`

### O que foi feito:
1. **arquivo.ext** — Descrição técnica curta da mudança.

### Por quê:
Motivação em 1-2 frases.
```

Isto é **obrigatório**. O dono do projeto usa este log para rastrear todas as mudanças feitas por IAs.
