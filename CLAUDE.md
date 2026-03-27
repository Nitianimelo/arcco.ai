# CLAUDE.md — Guia de Referência do Repositório Arcco

> Leia este arquivo inteiro antes de sugerir ou fazer qualquer mudança.

---

## 1. O QUE É O ARCCO

Arcco é uma plataforma SaaS de IA focada em chat inteligente com agentes autônomos.

| Produto | O que faz |
|---|---|
| **Arcco Chat** | Chat principal com agentes autônomos (busca web, geração de arquivos, execução Python, browser, skills dinâmicas) |
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
│   │   ├── orchestrator.py         # Pipeline: Planner → Supervisor ReAct → Workers + Skills
│   │   └── executor.py             # Executa tools: E2B Python (com auto-healing), Browser, Files, Web Search
│   ├── api/
│   │   ├── chat.py                 # POST /api/agent/chat → orchestrate_and_stream()
│   │   ├── admin.py                # Admin API: GET/PUT/reset agentes, GET models
│   │   ├── export.py               # POST /api/agent/export-doc, export-html (com opções de slide/tamanho/resolução)
│   │   ├── search.py               # POST /api/agent/search
│   │   ├── files.py                # POST /api/agent/files (PDF, Excel, PPTX)
│   │   ├── ocr.py                  # POST /api/agent/ocr
│   │   └── router.py               # POST /api/agent/route
│   ├── services/
│   │   ├── search_service.py       # Integração Tavily
│   │   ├── file_service.py         # PDF (Playwright/reportlab), Excel, PPTX, DOCX, Screenshot — viewport responsivo
│   │   ├── ocr_service.py          # OCR de imagens
│   │   ├── browser_service.py      # Browserbase + Playwright CDP (navigate, scrape, fill, click)
│   │   ├── session_file_service.py # Upload, OCR e gestão de arquivos por sessão
│   │   ├── ephemeral_rag_service.py# RAG lexical efêmero (chunking + ranking por frequência)
│   │   ├── session_gc_service.py   # Garbage collector de sessões expiradas
│   │   ├── apify_service.py        # SimilarWeb scraping via Apify
│   │   └── chat_models.py          # CRUD de slots de chat mode
│   └── skills/                     # Skills Dinâmicas — auto-descobertas pelo loader
│       ├── __init__.py             # Documentação e template de skill
│       ├── base.py                 # SkillMeta TypedDict (contrato)
│       ├── loader.py               # Descoberta automática, filtragem por keywords, execução
│       ├── slide_generator.py      # Gera estrutura JSON de apresentações (copywriter + UX)
│       ├── web_form_operator.py    # RPA: preenche formulários web via browser + LLM
│       ├── lead_extractor.py       # SDR: extrai leads de empresas via E2B + DuckDuckGo
│       └── multi_doc_investigator.py # Investigador multi-documento (RAG lexical + síntese LLM)
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
│       ├── PresentationCard.tsx    # Card de design: 16:9 para apresentações, 1:1 para single-page
│       ├── DesignPreviewModal.tsx  # Modal preview/edição: iframe+nav para apresentações, Fabric.js para designs
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
├── AI_CHANGELOG.md                 # Log obrigatório de todas as mudanças feitas por IAs
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
      │     → Skills dinâmicas são injetadas no prompt por relevância (keywords)
      │
      ├─ 2a. is_complex=true → PLANNER LOOP (determinístico)
      │     → Itera steps com tool_choice forçado por step.action
      │     → Suporta ações nativas (web_search, python, browser...) E skills dinâmicas
      │     → accumulated_context passa entre steps
      │
      └─ 2b. is_complex=false → REACT LOOP (Supervisor com SUPERVISOR_TOOLS + Skills)
            → MAX_ITERATIONS loop com tool calls
```

**Eventos SSE:** `steps` | `chunk` | `pre_action` | `thought` | `browser_action` | `text_doc` | `file_artifact` | `error`

**TOOL_MAP** (orchestrator.py):
- Terminal (resultado direto ao frontend): `ask_text_generator`, `ask_design_generator`
- Non-terminal (volta ao Supervisor): `ask_web_search`, `ask_browser`, `execute_python`, `deep_research`, `ask_file_modifier`, `read_session_file`
- Skills dinâmicas: detectadas via `skills_loader.is_skill()`, rota `dynamic_skill`, non-terminal

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

## 5. SKILLS DINÂMICAS

**Diretório:** `backend/skills/` — auto-descobertas pelo `loader.py` ao iniciar o backend.

**Como criar uma nova skill:**
1. Criar arquivo `.py` em `backend/skills/`
2. Definir `SKILL_META` (dict com id, name, description, keywords, parameters)
3. Definir `async def execute(args: dict) -> str`
4. Reiniciar backend — skill é descoberta automaticamente

**Skills existentes:**

| Skill ID | Arquivo | O que faz |
|---|---|---|
| `slide_generator` | `slide_generator.py` | Gera estrutura JSON de apresentações (copywriter + UX) |
| `web_form_operator` | `web_form_operator.py` | RPA: preenche formulários web via Browserbase + mapeamento LLM |
| `local_lead_extractor` | `lead_extractor.py` | SDR: busca leads de empresas via E2B sandbox + DuckDuckGo Search |
| `multi_doc_investigator` | `multi_doc_investigator.py` | Cruza informações de todos os documentos da sessão via RAG lexical |

**Fluxo de execução:**
```
Planner gera step.action = "skill_id"
  → orchestrator detecta via skills_loader.is_skill()
  → força tool_choice para o skill_id
  → executa via skills_loader.execute_dynamic_skill()
  → resultado volta ao accumulated_context (non-terminal)
```

**Keywords:** cada skill define keywords que filtram quando ela é injetada no prompt do Planner/Supervisor. Se o intent do usuário não contém nenhuma keyword, a skill NÃO é injetada (economia de tokens).

---

## 6. AUTO-HEALING (Execute Python)

**Arquivo:** `backend/agents/executor.py` → `_execute_python()`

Quando o LLM gera código Python com erro (import faltando, syntax error, etc.), o executor corrige automaticamente:

```
1. Executa código no E2B Sandbox
2. Se erro detectado:
   → Chama gpt-4o-mini: "reescreva o código corrigindo: {erro}"
   → Re-executa código corrigido
   → Até 2 retries (3 tentativas total)
3. Se sucesso em qualquer tentativa → retorna resultado
4. Se falhou 3x → retorna erro formatado ao orchestrator
```

Isso é **invisível** para o orchestrator e frontend — só aparece nos logs do terminal.

---

## 7. SISTEMA DE APRESENTAÇÕES (Multi-Slide)

**Detecção:** regex em `<div class="slide"` — se encontrar 2+ elementos, ativa modo apresentação.

**PresentationCard.tsx:**
- Apresentações: thumbnail 16:9, mostra só o 1o slide, badge com contagem
- Designs single-page: thumbnail 1:1 (quadrado)

**DesignPreviewModal.tsx — dois modos:**
- **Apresentação:** iframe viewer + navegação de slides (prev/next, dots, teclado, postMessage)
- **Design single-page:** editor Fabric.js com sidebar (texto, cor, fonte, alinhamento)

**Export com opções (só apresentações):**
- Escolher: todos os slides ou slide atual
- PDF/PPTX: tamanho da página (Widescreen, A4, Letter)
- PNG/JPEG: resolução (HD 720, Full HD 1080)
- Multi-slide PNG/JPEG → ZIP com imagens individuais
- Viewport do Playwright muda ANTES da captura → CSS responsivo reflui conteúdo

**file_service.py — funções de export:**
- `generate_pdf_playwright(html, slide_index, page_size)` → PDF multi-página
- `html_to_pptx(html, title, slide_index, page_size)` → PPTX com dimensões dinâmicas
- `html_to_screenshot(html, fmt, slide_index, resolution)` → imagem ou ZIP
- `_SHOW_SLIDE_JS` → JS robusto que isola cada slide para screenshot (força visibility, position, reflow)

---

## 8. VARIÁVEIS DE AMBIENTE

```env
OPENROUTER_API_KEY=...      # Carregada do Supabase (tabela ApiKeys)
OPENROUTER_MODEL=...        # Modelo default (override pelo registry)
SUPABASE_URL=...
SUPABASE_KEY=...
CORS_ORIGINS=...
TAVILY_API_KEY=...
E2B_API_KEY=...             # Obrigatório para execução Python (sandbox cloud)
BROWSERBASE_API_KEY=...     # Para browser agent e skill RPA
BROWSERBASE_PROJECT_ID=...
```

---

## 9. COMO RODAR LOCALMENTE

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

## 10. REGRAS PARA EDIÇÃO

1. **Nunca altere o contrato SSE** sem atualizar emitter (Python) e consumer (TypeScript)
2. **O registry é a fonte da verdade** para prompts/modelos em produção
3. **`configs_override.json`** é gerado automaticamente pelo admin — não commitar manualmente
4. **Respostas ao usuário:** nunca retornar `**`, `#` ou markdown (exceto links `[texto](url)`)
5. **E2B v2.4.1:** usar `Sandbox.create(api_key=...)`, não o construtor. Output de print() está em `result.logs.stdout`
6. **Export PDF:** tem fallback reportlab quando Playwright não está disponível
7. **Tools no orchestrator:** sempre dentro de try/except para não matar o generator SSE
8. **Skills:** cada skill é um arquivo .py isolado em `backend/skills/`. Nunca modificar o `loader.py` para adicionar uma skill — ele descobre automaticamente.
9. **Auto-healing:** o loop de auto-correção no executor é interno. Não tratar erros de Python no orchestrator — o executor já resolve.

---

## 11. CHANGELOG OBRIGATÓRIO

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
