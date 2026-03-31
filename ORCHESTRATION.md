# ORCHESTRATION.md — Arquitetura de Orquestração do Arcco

> Documento técnico completo para qualquer IA ou desenvolvedor entender o sistema de orquestração multi-agente do Arcco. Leia este arquivo antes de fazer qualquer modificação no pipeline de execução.

---

## 1. VISÃO GERAL

O Arcco usa uma arquitetura **Supervisor-Worker multi-agente** com um **Planejador determinístico** que opera em dois modos distintos. Todo o fluxo começa com uma mensagem do usuário e termina com eventos SSE (Server-Sent Events) transmitidos ao frontend em tempo real.

```
Mensagem do Usuário
       ↓
  [PLANNER] — gpt-4o-mini, temperature=0.1
       ↓
  is_complex?
  ├── SIM → [PLANNER LOOP] — execução determinística passo a passo
  └── NÃO → [REACT LOOP]  — execução reativa com MAX_ITERATIONS=3
       ↓
  Eventos SSE → Frontend (ArccoChat.tsx)
```

---

## 2. ENTRADA DO PIPELINE

**Endpoint:** `POST /api/agent/chat`
**Arquivo:** `backend/api/chat.py`

```python
{
  "messages": [...],          # histórico completo da conversa
  "mode": "agent" | "normal", # agent = orquestração, normal = chat direto
  "session_id": "...",        # ID da sessão para arquivos efêmeros
  "user_id": "...",           # ID do usuário autenticado
  "project_id": "...",        # ID do projeto (opcional)
  "conversation_id": "...",   # ID da conversa para persistência
  "web_search": true,         # habilita busca web no modo normal
  "computer_enabled": true,   # habilita Arcco Computer (arquivos do usuário)
  "spy_pages_enabled": true,  # habilita análise SimilarWeb
  "fast_model": "..."         # modelo rápido para dual-model no modo normal
}
```

No modo `normal`, o chat usa `_stream_normal_chat()` com suporte a dual-model (fast_model → ESCALATE → expert_model). No modo `agent`, chama `orchestrate_and_stream()` do orchestrator.

---

## 3. FASE 1 — O PLANNER

**Arquivo:** `backend/agents/planner.py`
**Arquivo de prompt:** `backend/agents/prompts.py` → `PLANNER_SYSTEM_PROMPT`
**Modelo padrão:** `openai/gpt-4o-mini` (editável via admin, agent_id=`planner`)
**Temperature:** `0.1` (baixa para saída determinística)
**Max tokens:** `1500`

### O que o Planner faz

1. Recebe o pedido do usuário como texto
2. Injeta dinamicamente as skills disponíveis filtradas por keyword matching
3. Chama o LLM com o schema Pydantic como instrução de output
4. Retorna um `PlannerOutput` com JSON validado

### Schema de saída (Pydantic)

```python
class PlanStep(BaseModel):
    step: int           # número do passo (1-indexed)
    action: str         # "web_search" | "python" | "browser" | "file_modifier" |
                        # "text_generator" | "design_generator" | "deep_research" |
                        # "direct_answer" | "<skill_id>"
    detail: str         # descrição detalhada do que o passo deve fazer
    is_terminal: bool   # True APENAS no último passo (entregável final)

class PlannerOutput(BaseModel):
    is_complex: bool                        # True = Planner Loop, False = ReAct Loop
    steps: List[PlanStep]                   # lista ordenada de passos
    acknowledgment: str                     # frase de confirmação ao usuário
    needs_clarification: bool               # True se pedido é ambíguo
    questions: List[ClarificationQuestion]  # max 3 perguntas (só se needs_clarification)
```

### Injeção dinâmica de skills

Antes de chamar o LLM, o planner filtra as skills disponíveis por keyword matching com o intent do usuário via `skills_loader.get_skill_descriptions(user_intent)`. Só skills relevantes são injetadas — evita poluir o contexto com skills irrelevantes.

### Fallback em caso de falha

Se o LLM retornar JSON inválido ou ocorrer qualquer erro, o planner retorna:
```python
PlannerOutput(is_complex=False, steps=[PlanStep(step=1, action="direct_answer", detail=user_intent)])
```

---

## 4. FASE 2A — PLANNER LOOP (is_complex=True)

**Arquivo:** `backend/agents/orchestrator.py`
**Condição de ativação:** `plan_output.is_complex == True`

### Fluxo por passo

```
Para cada step em plan_output.steps:
  1. Monta contexto acumulado (resultados dos passos anteriores)
  2. Chama _call_supervisor_for_step(step, accumulated_context)
     → Supervisor recebe tool_choice forçado para o step.action
  3. Extrai tool_call do response
  4. Executa a ferramenta via execute_tool()
  5. IF step.is_terminal == True:
       → Emite resultado direto ao frontend e ENCERRA o pipeline
     ELSE:
       → Acumula resultado em accumulated_context
       → Continua para o próximo passo

Após todos os passos não-terminais:
  → Chama Supervisor novamente para consolidar accumulated_context
  → Supervisor escreve resposta final em linguagem natural
  → Streaming dos chunks para o frontend
```

### accumulated_context

A variável `accumulated_context` é uma string que cresce a cada passo:
```
[Step 1 - web_search]: <resultado da busca>
[Step 2 - python]: <output do código>
...
```
O Supervisor recebe esse contexto completo ao ser chamado para o passo seguinte ou para a resposta final, garantindo que cada passo "enxerga" o que foi feito antes.

### Forced tool_choice

O Supervisor é chamado com `tool_choice={"type": "function", "function": {"name": tool_name}}` para forçar o uso exato da ferramenta planejada. Se o modelo não suportar forced tool_choice (alguns modelos no OpenRouter), o sistema cai para `tool_choice="auto"` e instrui o modelo via texto. O mapeamento de `step.action` para `tool_name` está em `_PLANNER_ACTION_TO_TOOL` no orchestrator.py.

---

## 5. FASE 2B — REACT LOOP (is_complex=False)

**Arquivo:** `backend/agents/orchestrator.py`
**Condição de ativação:** `plan_output.is_complex == False`
**MAX_ITERATIONS:** `3`

### Fluxo

```
Iteração 1, 2, 3:
  → Chama Supervisor com SUPERVISOR_TOOLS (tool_choice="auto")
  → Se tool_call presente:
      → Executa a ferramenta
      → IF is_terminal: encerra e emite resultado
      → IF não terminal: acumula resultado, continua
  → Se sem tool_call:
      → Supervisor responde diretamente em linguagem natural
      → Stream dos chunks para o frontend

Após MAX_ITERATIONS sem resolução:
  → Emite mensagem de erro
```

---

## 6. TOOL_MAP — TERMINAL VS NÃO-TERMINAL

**Arquivo:** `backend/agents/orchestrator.py`

| Ferramenta | Route | is_terminal |
|---|---|---|
| `ask_text_generator` | text_generator | **SIM** |
| `ask_design_generator` | design_generator | **SIM** |
| `ask_web_search` | web_search | não |
| `ask_browser` | browser | não |
| `execute_python` | python | não |
| `deep_research` | deep_research | não |
| `ask_file_modifier` | file_modifier | não |
| `read_session_file` | session_file | não |
| `analyze_web_pages` | spy_pages | não |
| `list_computer_files` | computer | não |
| `read_computer_file` | computer | não |
| `manage_computer_file` | computer | não |
| Skills dinâmicas | dynamic_skill | não |

**Regra:** ferramentas terminais encerram o pipeline imediatamente após execução — o resultado vai direto ao frontend. Ferramentas não-terminais acumulam contexto e o Supervisor continua trabalhando.

---

## 7. REGISTRO DE AGENTES (7 AGENTES BASE)

**Arquivo:** `backend/agents/registry.py`
**Persistência:** 4 camadas — memória → Supabase → configs_override.json → prompts.py/tools.py

| agent_id | Nome | Modelo padrão | Ferramentas | Editável admin |
|---|---|---|---|---|
| `chat` | Supervisor | default_model | SUPERVISOR_TOOLS | sim |
| `planner` | Master Planner | gpt-4o-mini | [] | sim |
| `web_search` | Busca Web | default_model | WEB_SEARCH_TOOLS | sim |
| `text_generator` | Gerador de Texto | default_model | [] | sim |
| `design_generator` | Design | default_model | [] | sim |
| `file_modifier` | Modificador | default_model | FILE_MODIFIER_TOOLS | sim |
| `qa` | QA | default_model | [] | sim |

**Acesso via registry:**
```python
registry.get_prompt("chat")    # → CHAT_SYSTEM_PROMPT (editável)
registry.get_model("chat")     # → modelo ativo (default ou override)
registry.get_tools("chat")     # → SUPERVISOR_TOOLS
registry.update_agent("chat", {"model": "anthropic/claude-3.5-sonnet"})
```

---

## 8. FERRAMENTAS DO SUPERVISOR (SUPERVISOR_TOOLS)

**Arquivo:** `backend/agents/tools.py` → `SUPERVISOR_TOOLS`
**Execução:** `backend/agents/executor.py` → `execute_tool(func_name, func_args)`

### Ferramentas disponíveis

**Arquivos da sessão:**
- `read_session_file(session_id, file_name, query?)` → lê arquivo anexado com RAG lexical opcional

**Especialistas terminais:**
- `ask_text_generator(title_hint, instructions, content_brief)` → gera documento longo em `<doc>`
- `ask_design_generator(title_hint, instructions, content_brief, design_direction?)` → gera HTML visual

**Especialistas não-terminais:**
- `ask_web_search(query, fetch_url?)` → busca Tavily + fetch opcional de URL
- `ask_browser(url, actions[], wait_for?, mobile?, include_tags?, exclude_tags?)` → Browserbase CDP
- `execute_python(code)` → sandbox E2B com auto-healing (até 2 retries automáticos)
- `ask_file_modifier(file_url?, session_id?, file_name?, instructions)` → modifica PDF/Excel/PPTX
- `deep_research(query, context?)` → pesquisa multi-site assíncrona (1-3 min)
- `analyze_web_pages(urls[])` → métricas SimilarWeb via Apify (máx 4 URLs)

**Arcco Computer (condicional — computer_enabled=True):**
- `list_computer_files(folder_path?)` → lista arquivos do usuário
- `read_computer_file(file_id, query?)` → lê arquivo com extração de texto
- `manage_computer_file(action, ...)` → move/renomeia/cria pasta/salva

### Auto-healing do execute_python

```
1. Executa código no E2B Sandbox
2. SE erro detectado:
   → Chama gpt-4o-mini: "reescreva corrigindo: {erro}"
   → Re-executa código corrigido
   → Até 2 retries (3 tentativas total)
3. SE sucesso em qualquer tentativa → retorna resultado
4. SE falhou 3x → retorna erro formatado ao orchestrator
```

### Publicação automática de artefatos

Se o código Python salvar arquivos em `/tmp/`, o executor detecta, faz upload para o Supabase Storage e emite o evento SSE `file_artifact` com o link de download. Profundidade de varredura: 8 níveis. Limite: 20MB por arquivo.

---

## 9. SKILLS DINÂMICAS

**Diretório:** `backend/skills/`
**Auto-descoberta:** loader.py ao iniciar o backend

### Como funciona

1. Cada skill é um arquivo `.py` independente com `SKILL_META` + `async def execute(args)`
2. O `loader.py` descobre todas automaticamente ao iniciar
3. O Planner filtra skills por keyword matching com o intent do usuário
4. Se keywords batem, a skill é injetada no prompt do Planner/Supervisor
5. O Supervisor chama a skill como uma tool normal
6. O resultado é acumulado como contexto não-terminal

### Skills disponíveis

| Skill ID | Arquivo | O que faz |
|---|---|---|
| `slide_generator` | `slide_generator.py` | Roteiriza estrutura JSON de apresentações |
| `web_form_operator` | `web_form_operator.py` | RPA: preenche formulários web via Browserbase + LLM |
| `local_lead_extractor` | `lead_extractor.py` | Prospecção de leads via E2B + DuckDuckGo |
| `multi_doc_investigator` | `multi_doc_investigator.py` | RAG lexical cruzando múltiplos docs da sessão |

### Como criar uma nova skill

```python
# backend/skills/minha_skill.py

SKILL_META = {
    "id": "minha_skill",
    "name": "Nome da Skill",
    "description": "O que ela faz em uma frase.",
    "keywords": ["palavra1", "palavra2"],   # filtro para injeção no Planner
    "parameters": {
        "param1": {"type": "string", "description": "...", "required": True},
    }
}

async def execute(args: dict) -> str:
    # lógica da skill
    return "resultado como string"
```

Reinicie o backend — a skill é descoberta automaticamente. Sem modificar loader.py.

---

## 10. EVENTOS SSE (Server-Sent Events)

**Formato:** `data: {"type": "...", "content": "..."}\n\n`
**Consumer:** `pages/ArccoChat.tsx` via `agentApi.chat()` em `lib/api-client.ts`

| Evento | Quando é emitido | O que o frontend faz |
|---|---|---|
| `pre_action` | Antes de chamar uma ferramenta | Exibe acknowledgment com estilo leve |
| `steps` | Durante execução do passo | Exibe no AgentTerminal |
| `thought` | Raciocínio interno do agente | Exibe no AgentThoughtPanel |
| `chunk` | Streaming da resposta final | Acumula no balão de chat |
| `text_doc` | Documento gerado pelo text_generator | Exibe TextDocCard com preview/export |
| `file_artifact` | Arquivo gerado pelo Python/file_generator | Exibe ArtifactCard com download |
| `browser_action` | Ações do navegador (navegando/concluído/erro) | Exibe BrowserAgentCard |
| `clarification` | Planner precisa de input do usuário | Exibe modal com perguntas |
| `spy_pages_result` | Resultado do SimilarWeb | Card especial com métricas |
| `thinking_upgrade` | Dual-model: escalou para modelo especialista | Muda animação de thinking (1 dot → 3 dots) |
| `error` | Exceção no pipeline | Exibe caixa de erro vermelha |
| `conversation_id` | ID da conversa para persistência | Salva no localStorage |

---

## 11. SISTEMA DE PROMPTS — ARQUITETURA XML

**Arquivo:** `backend/agents/prompts.py`

Os prompts foram reescritos com estrutura XML semântica e lógica IF/THEN explícita.

### CHAT_SYSTEM_PROMPT (Supervisor) — estrutura

```xml
<identity>
  Identidade, idioma, missão principal do Arcco
</identity>

<core_constraints>
  5 regras absolutas inegociáveis — repetidas no topo E no final (padrão sanduíche)
  para combater o efeito "Lost in the Middle" em contextos longos
</core_constraints>

<tool_routing>
  <tool id="ask_web_search"> IF/THEN + quando NÃO usar </tool>
  <tool id="ask_browser">    IF/THEN + CoT obrigatório + quando NÃO usar </tool>
  <tool id="execute_python"> IF/THEN + CoT obrigatório + quando NÃO usar </tool>
  <tool id="ask_text_generator">    IF/THEN </tool>
  <tool id="ask_design_generator">  IF/THEN </tool>
  <tool id="ask_file_modifier">     IF/THEN </tool>
  <tool id="deep_research">         IF/THEN + quando NÃO usar </tool>
  <tool id="read_session_file">     IF/THEN </tool>
  <tool id="dynamic_skills">        IF/THEN por skill </tool>
</tool_routing>

<response_format>
  Como formatar resposta após cada tipo de ferramenta
</response_format>

<autonomous_behavior>
  Mock data, sem confirmações, ação imediata
</autonomous_behavior>

<prohibited_behaviors>
  8 proibições absolutas com exemplos ERRADO vs CORRETO
</prohibited_behaviors>

<core_constraints_reminder>
  Repetição das 5 regras críticas (sandwich final)
</core_constraints_reminder>
```

### PLANNER_SYSTEM_PROMPT — estrutura

```xml
<identity>
  Planner não conversa, só gera JSON
</identity>

<available_tools>
  <tool id="web_search"> quando usar + quando NÃO usar </tool>
  <!-- ... 7 ferramentas no total ... -->
</available_tools>

<decision_tree>
  Árvore IF/THEN cobrindo todos os cenários de roteamento
</decision_tree>

<anti_patterns>
  6 planos ERRADOS com exemplos explícitos + versão CORRETA
</anti_patterns>

<output_rules>
  Regras de geração do JSON: minimização, is_terminal, acknowledgment
</output_rules>
```

### Por que XML?

1. **Mecanismo de atenção dos Transformers** responde melhor a delimitadores explícitos que a listas markdown
2. **Tags XML comunicam escopo** — o modelo sabe exatamente quando uma regra começa e termina
3. **Escalável** — ao adicionar skills e ferramentas, o modelo não "perde" regras antigas
4. **Padrão sanduíche** combate o efeito "Lost in the Middle" (Nelson et al., 2023): regras críticas no topo E no final aumentam a probabilidade de serem respeitadas

### Chain of Thought seletivo

`ask_browser` e `execute_python` exigem que o Supervisor escreva um parágrafo de raciocínio ANTES de chamar a ferramenta. Isso:
- Aumenta a precisão das ações complexas
- É exibido ao usuário como progresso via evento SSE `thought`
- É aplicado apenas em ferramentas de alto custo de erro (não em ask_web_search)

---

## 12. PAINEL ADMIN — COMO AS MUDANÇAS CHEGAM LÁ

**Frontend:** `pages/AdminPage.tsx`
**Backend API:** `backend/api/admin.py`

### Abas do painel

| Aba | O que mostra | O que edita |
|---|---|---|
| Orquestração | 7 agentes com prompt, modelo, tools | Prompts (regex em prompts.py), Tools (AST em tools.py), Modelos (Supabase) |
| Modelos | Slots de chat mode configuráveis | Tabela `chat_model_configs` no Supabase |
| Custos | Uso de tokens por usuário e modelo | Tabela `token_usage` no Supabase (somente leitura) |

### Fluxo de edição de prompt via admin

```
Usuário edita prompt no painel
       ↓
PUT /api/agent/admin/agents/{agent_id}
       ↓
admin.py → _write_prompt_to_source(constant, new_prompt)
  → Regex: ^CONSTANT_NAME\s*=\s*""".*?""" (re.MULTILINE | re.DOTALL)
  → Substitui o bloco inteiro no arquivo prompts.py
  → Triple-quotes no conteúdo são convertidas para ''' antes de salvar
       ↓
registry.update_agent(agent_id, {"system_prompt": new_prompt})
  → Atualiza em memória
       ↓
Uvicorn com --reload detecta mudança no .py e reinicia automaticamente
```

### Fluxo de edição de modelo via admin

```
Usuário seleciona novo modelo no painel
       ↓
PUT /api/agent/admin/agents/{agent_id}
       ↓
admin.py → save_agent_model_override(agent_id, model_id)
  → Salva na tabela Supabase agent_model_overrides
  → Fallback: salva em configs_override.json
       ↓
registry.update_agent() atualiza em memória
```

### Formato do endpoint de agentes

```http
GET /api/agent/admin/agents
→ [{ "id": "chat", "name": "Supervisor", "system_prompt": "...", "model": "...", "tools": [...] }, ...]

PUT /api/agent/admin/agents/{agent_id}
body: { "system_prompt"?: "...", "model"?: "...", "tools"?: [...] }
→ { "success": true, "errors": [...] }

POST /api/agent/admin/agents/{agent_id}/reset
→ Restaura prompt/tools para os valores originais do código
```

---

## 13. PIPELINE DE QA (Validação de Especialistas)

**Arquivo:** `backend/agents/orchestrator.py` → `_run_specialist_with_qa()`
**Agente:** `qa` (agent_id=`qa`)

Apenas o agente `file_modifier` passa pelo QA. O QA avalia a saída e pode solicitar retrabalho:

```
1ª tentativa: especialista executa
  → QA avalia: {"approved": bool, "issues": [...], "correction_instruction": "..."}
  → SE aprovado: retorna resultado
  → SE reprovado E tentativas < 2:
      → Appenda resposta do especialista + feedback do QA nas mensagens
      → Chama especialista novamente com correção
      → MAX_QA_RETRIES = 2

Regra fail-open do QA: aprova a menos que haja falha fatal.
Se o resultado cumpre a função básica, APROVE IMEDIATAMENTE.
```

---

## 14. MODO DUAL-MODEL (Chat Normal)

**Arquivo:** `backend/api/chat.py` → `_stream_normal_chat()`

Quando `fast_model` está configurado no slot de chat mode:

```
1. Chama fast_model (não-streaming, max_tokens=800, temperature=0.3)
   com prompt: "Responda diretamente OU responda ESCALATE se for complexo"
       ↓
2. SE fast_model responde diretamente:
   → Emite resposta como chunk(s) → FIM
       ↓
3. SE fast_model retorna "ESCALATE":
   → Emite evento SSE: {"type": "thinking_upgrade"}
   → Frontend muda animação: 1 dot pulsante → 3 dots bouncing
   → Chama expert_model em streaming → chunks → FIM
```

O usuário nunca vê "ESCALATE". A transição é invisível, com apenas uma mudança de animação indicando maior profundidade de raciocínio.

---

## 15. GESTÃO DE SESSÃO E ARQUIVOS EFÊMEROS

**Serviços:**
- `backend/services/session_file_service.py` — upload, OCR, gestão por session_id
- `backend/services/ephemeral_rag_service.py` — RAG lexical (chunking + ranking por frequência)
- `backend/services/session_gc_service.py` — garbage collector de sessões expiradas

**Inventário de arquivos:** Ao iniciar cada request de orquestração, o sistema injeta uma mensagem de sistema com os arquivos disponíveis na sessão:
```
"Arquivos anexados nesta sessão: relatorio.pdf (ready), dados.xlsx (processing)"
```
O Supervisor usa essa informação para decidir quando chamar `read_session_file`.

**GC throttled:** O garbage collector é chamado via `_maybe_run_gc()` com throttle de 5 minutos. Roda em background via `asyncio.ensure_future()` — não bloqueia requests.

---

## 16. CONEXÃO COM SUPABASE

**Arquivo:** `backend/core/supabase_client.py`

- Singleton `httpx.Client` com connection pooling (max 20 conexões, 10 keep-alive)
- Chaves da API carregadas assincronamente no startup via `asyncio.to_thread()`
- Cache de 5 minutos para a chave E2B (`_e2b_key_cache`) — evita N+1 queries no Supabase

**Tabelas principais:**

| Tabela | O que armazena |
|---|---|
| `api_keys` | Chaves OPENROUTER_API_KEY, E2B_API_KEY, etc. |
| `agent_model_overrides` | Modelos customizados por agent_id |
| `chat_model_configs` | Slots de chat mode (nome, modelo, system prompt, fast_model_id) |
| `token_usage` | Rastreamento de tokens por usuário/modelo |
| `conversations` | Histórico de conversas para persistência |
| `session_files` | Metadados de arquivos anexados em sessões efêmeras |

---

## 17. CONSTANTES E LIMITES DO SISTEMA

```python
# Timeouts
_BROWSER_TIMEOUT = 60.0       # segundos para operações browser
_SEARCH_TIMEOUT = 30.0        # segundos para busca web
_HEARTBEAT_INTERVAL = 5.0     # frequência de heartbeat SSE

# Loops
MAX_ITERATIONS = 3            # ReAct loop
MAX_QA_RETRIES = 2            # retries do QA
max_iterations = 5            # loop interno de especialistas
_MAX_AUTOFIX = 2              # auto-healing Python (3 tentativas total)

# Cache
_E2B_KEY_CACHE_TTL = 300.0    # 5 minutos cache da chave E2B
_GC_INTERVAL_SECONDS = 300.0  # 5 minutos entre execuções do GC

# Limites de arquivo
_E2B_ARTIFACT_MAX_BYTES = 20 * 1024 * 1024  # 20MB por artefato
_E2B_ARTIFACT_SCAN_DEPTH = 8                 # profundidade de varredura em /tmp/

# Truncamento de texto
web fetch: 20.000 chars
session file preview: 3.000 chars
computer file preview: 4.000 chars
PDF pages: para após 4.000 chars total
```

---

## 18. COMO ADICIONAR UMA NOVA FERRAMENTA AO SUPERVISOR

1. **executor.py** — adicionar o handler `_minha_ferramenta()` e o case no `execute_tool()`
2. **tools.py** — adicionar a definição JSON em `SUPERVISOR_TOOLS`
3. **orchestrator.py** — adicionar entrada no `TOOL_MAP` com `route` e `is_terminal`
4. **prompts.py** — adicionar bloco `<tool id="minha_ferramenta">` no `CHAT_SYSTEM_PROMPT` e regra correspondente no `PLANNER_SYSTEM_PROMPT`
5. Reiniciar o backend

---

## 19. COMO RODAR LOCALMENTE

```bash
# Backend (porta 8001)
E2B_API_KEY="sua_chave" uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (porta 3000)
npm run dev
```

**Dependências Python extras:**
```bash
pip install e2b-code-interpreter browserbase playwright
playwright install chromium
```

---

## 20. DIAGRAMA COMPLETO DO PIPELINE

```
Mensagem do Usuário
       ↓
POST /api/agent/chat
       ↓
orchestrate_and_stream()
       ↓
  [PLANNER] gpt-4o-mini, temp=0.1
  ├─ Injeta skills por keyword matching
  └─ Retorna PlannerOutput JSON
       ↓
  is_complex?
  │
  ├─── SIM → [PLANNER LOOP]
  │    │
  │    ├─ step 1: Supervisor forced_tool_choice → executa tool → acumula
  │    ├─ step 2: Supervisor forced_tool_choice → executa tool → acumula
  │    ├─ ...
  │    └─ step N (terminal): executa → emite SSE → ENCERRA
  │         OU
  │         Após últimos steps → Supervisor consolida → stream resposta final
  │
  └─── NÃO → [REACT LOOP] MAX_ITER=3
       │
       ├─ Supervisor auto tool_choice → executa → acumula/encerra
       ├─ (repete até sem tool_call ou terminal)
       └─ Supervisor responde diretamente → stream

Eventos SSE durante todo o processo:
  pre_action → steps → thought → chunk → text_doc → file_artifact
  browser_action → clarification → spy_pages_result → error
```

---

*Última atualização: 2026-03-31 — Claude Code (claude-sonnet-4-6)*
