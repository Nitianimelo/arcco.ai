# CHANGELOG — Registro de Modificações por IA

> Toda IA que modificar código neste repositório DEVE registrar aqui.
> Formato: data/hora, arquivos modificados, o que foi feito, por quê.

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
